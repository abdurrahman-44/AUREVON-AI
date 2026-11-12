import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database.session import get_db
from backend.app.api.deps import get_optional_user, assert_resource_ownership
from backend.app.models.entities import Document, DocumentChunk, User
from backend.app.schemas.document import (
    DocumentResponse,
    DocumentQueryRequest,
    DocumentQueryResponse,
    DocumentChunkResult,
)
from backend.app.services.documents.extractor import DocumentExtractor
from backend.app.services.documents.chunker import TextChunker
from backend.app.services.documents.embeddings import EmbeddingService
from backend.app.services.documents.rag import RAGService
from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limit_dependency

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".py", ".js", ".ts"}
MAX_FILE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_dependency("upload", lambda: settings.RATE_LIMIT_UPLOAD_PER_MINUTE))],
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    raw_name = file.filename or "uploaded_file"
    filename = os.path.basename(raw_name).replace("..", "") or "uploaded_file"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # Ensure upload directory exists and avoid filename collisions / traversal
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    storage_path = os.path.join(settings.UPLOAD_DIR, unique_name)

    # Save to disk
    with open(storage_path, "wb") as f:
        f.write(content)

    user_id = current_user.id if current_user else None

    # Create document record
    doc = Document(
        user_id=user_id,
        filename=filename,
        file_type=ext.replace(".", ""),
        file_size_bytes=file_size,
        storage_path=storage_path,
        processing_status="processing",
    )
    db.add(doc)
    await db.flush()

    # Extract text
    try:
        pages = DocumentExtractor.extract(content, filename)
        chunker = TextChunker(chunk_size=500, chunk_overlap=80)
        chunks_data = chunker.chunk_document(pages)

        # Generate embeddings & save chunks
        chunk_count = 0
        for item in chunks_data:
            emb = await EmbeddingService.get_embedding(item["content"])
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=item["chunk_index"],
                content=item["content"],
                page_number=item["page_number"],
                embedding=emb,
            )
            db.add(chunk)
            chunk_count += 1

        doc.chunk_count = chunk_count
        doc.processing_status = "completed"
        await db.commit()
        await db.refresh(doc)
    except Exception as e:
        doc.processing_status = f"failed: {str(e)}"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

    return doc


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document)
    if current_user:
        stmt = stmt.where(Document.user_id == current_user.id)
    else:
        stmt = stmt.where(Document.user_id.is_(None))
    stmt = stmt.order_by(Document.created_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    assert_resource_ownership(doc.user_id, current_user, "document")
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    assert_resource_ownership(doc.user_id, current_user, "document")

    if os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except Exception:
            pass

    await db.delete(doc)
    await db.commit()
    return None


@router.post("/query", response_model=DocumentQueryResponse)
async def query_documents(
    payload: DocumentQueryRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user.id if current_user else None
    results = await RAGService.retrieve_relevant_chunks(
        session=db,
        query=payload.query,
        user_id=user_id,
        top_k=payload.top_k or 4,
        min_similarity=payload.min_similarity or 0.2,
    )

    items = [
        DocumentChunkResult(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            filename=r["filename"],
            page_number=r.get("page_number"),
            content=r["content"],
            similarity=r["similarity"],
        )
        for r in results
    ]

    return DocumentQueryResponse(
        query=payload.query,
        results=items,
        total_found=len(items),
    )
