import React, { useState } from 'react';
import { Eye, Shield, UserCheck, UserX, X } from 'lucide-react';
import { fetchAdminUserDetail, updateAdminUserRole, updateAdminUserStatus } from '../../services/api';
import { AdminUserDetailResponse, AdminUserItem, PaginatedUsersResponse } from '../../types';

interface AdminUsersPageProps {
  currentUserId: string;
  usersData: PaginatedUsersResponse | null;
  page: number;
  search: string;
  roleFilter: string;
  statusFilter: string;
  onChangePage: (p: number) => void;
  onChangeSearch: (s: string) => void;
  onChangeRoleFilter: (r: string) => void;
  onChangeStatusFilter: (s: string) => void;
  onRefreshUsers: () => void;
  onNotice: (msg: string) => void;
  onError: (msg: string) => void;
}

export const AdminUsersPage: React.FC<AdminUsersPageProps> = ({
  currentUserId,
  usersData,
  page,
  search,
  roleFilter,
  statusFilter,
  onChangePage,
  onChangeSearch,
  onChangeRoleFilter,
  onChangeStatusFilter,
  onRefreshUsers,
  onNotice,
  onError,
}) => {
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<AdminUserDetailResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const handleToggleStatus = async (u: AdminUserItem) => {
    setBusyUserId(u.id);
    try {
      await updateAdminUserStatus(u.id, !u.is_active);
      onNotice(`${!u.is_active ? 'Reactivated' : 'Suspended'} account '${u.username}'.`);
      onRefreshUsers();
      if (selectedDetail?.id === u.id) {
        setSelectedDetail({ ...selectedDetail, is_active: !u.is_active });
      }
    } catch (err: any) {
      onError(err.message || 'Status update failed');
    } finally {
      setBusyUserId(null);
    }
  };

  const handleToggleRole = async (u: AdminUserItem) => {
    const nextRole = u.role === 'owner' ? 'user' : 'owner';
    setBusyUserId(u.id);
    try {
      await updateAdminUserRole(u.id, nextRole);
      onNotice(`Changed role of '${u.username}' to '${nextRole}'.`);
      onRefreshUsers();
      if (selectedDetail?.id === u.id) {
        setSelectedDetail({ ...selectedDetail, role: nextRole });
      }
    } catch (err: any) {
      onError(err.message || 'Role update failed');
    } finally {
      setBusyUserId(null);
    }
  };

  const handleInspect = async (userId: string) => {
    setLoadingDetail(true);
    try {
      const detail = await fetchAdminUserDetail(userId);
      setSelectedDetail(detail);
    } catch (err: any) {
      onError(err.message || 'Failed to inspect user profile');
    } finally {
      setLoadingDetail(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-4">
        <input
          type="text"
          value={search}
          onChange={(e) => {
            onChangeSearch(e.target.value);
            onChangePage(1);
          }}
          placeholder="Search username or email..."
          className="min-w-[220px] flex-1 rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
        />
        <select
          aria-label="Filter role"
          value={roleFilter}
          onChange={(e) => {
            onChangeRoleFilter(e.target.value);
            onChangePage(1);
          }}
          className="rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
        >
          <option value="all">All Roles</option>
          <option value="owner">Owner</option>
          <option value="user">User</option>
        </select>
        <select
          aria-label="Filter status"
          value={statusFilter}
          onChange={(e) => {
            onChangeStatusFilter(e.target.value);
            onChangePage(1);
          }}
          className="rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
        >
          <option value="all">All Statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-line bg-elevated/60 text-[11px] uppercase tracking-wider text-ink-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Account</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Activity</th>
              <th className="px-4 py-3 font-medium text-right">Usage</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {(usersData?.items || []).map((u) => {
              const isSelf = u.id === currentUserId;
              const isBusy = busyUserId === u.id;
              return (
                <tr key={u.id} className="hover:bg-elevated/40">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-ink">{u.username}</div>
                    <div className="text-[11px] text-ink-muted">{u.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${
                        u.role === 'owner'
                          ? 'bg-indigo-500/15 text-indigo-400'
                          : 'bg-elevated text-ink-secondary'
                      }`}
                    >
                      {u.role === 'owner' && <Shield className="h-3 w-3" />}
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded px-2 py-0.5 text-[10px] font-semibold ${
                        u.is_active
                          ? 'bg-emerald-500/15 text-emerald-500'
                          : 'bg-rose-500/15 text-rose-500'
                      }`}
                    >
                      {u.is_active ? 'Active' : 'Suspended'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[11px] text-ink-secondary">
                    <div>Joined: {new Date(u.created_at).toLocaleDateString()}</div>
                    <div className="text-ink-muted">
                      Last active: {u.last_active_at ? new Date(u.last_active_at).toLocaleString() : 'Never'}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right text-[11px] text-ink-secondary">
                    <div>{u.conversation_count} chats • {u.ai_request_count} AI reqs</div>
                    <div className="text-ink-muted">
                      Tokens: {u.total_tokens !== null && u.total_tokens !== undefined ? u.total_tokens.toLocaleString() : 'Unavailable'}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleInspect(u.id)}
                        disabled={loadingDetail}
                        className="inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-[11px] font-medium text-ink hover:bg-elevated"
                      >
                        <Eye className="h-3 w-3" />
                        Inspect
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleStatus(u)}
                        disabled={isBusy || isSelf}
                        title={isSelf ? 'Cannot suspend your own owner session' : ''}
                        className="inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-[11px] font-medium text-ink-secondary hover:bg-elevated disabled:opacity-40"
                      >
                        {u.is_active ? <UserX className="h-3 w-3 text-rose-500" /> : <UserCheck className="h-3 w-3 text-emerald-500" />}
                        {u.is_active ? 'Suspend' : 'Activate'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleRole(u)}
                        disabled={isBusy || isSelf}
                        className="rounded-lg border border-line px-2 py-1 text-[11px] font-medium text-ink-secondary hover:bg-elevated disabled:opacity-40"
                      >
                        {u.role === 'owner' ? 'Set User' : 'Promote'}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {(!usersData || usersData.items.length === 0) && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-ink-muted">
                  No user accounts match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {usersData && (
        <div className="flex items-center justify-between text-xs text-ink-secondary">
          <span>
            Showing page {usersData.page} of {usersData.total_pages} ({usersData.total} accounts)
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => onChangePage(page - 1)}
              className="rounded-lg border border-line bg-surface px-3 py-1 hover:bg-elevated disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= usersData.total_pages}
              onClick={() => onChangePage(page + 1)}
              className="rounded-lg border border-line bg-surface px-3 py-1 hover:bg-elevated disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {selectedDetail && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-xs">
          <div className="h-full w-full max-w-md overflow-y-auto border-l border-line bg-surface p-6 shadow-2xl space-y-5">
            <div className="flex items-start justify-between border-b border-line pb-4">
              <div>
                <h3 className="text-base font-semibold text-ink">{selectedDetail.username}</h3>
                <p className="text-xs text-ink-muted">{selectedDetail.email}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDetail(null)}
                className="rounded-lg p-1 text-ink-muted hover:bg-elevated"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="rounded-lg border border-line bg-elevated/60 p-3 text-[11px] text-ink-secondary">
              Privacy Guarantee: Passwords, API credentials, and private chat message contents are strictly omitted.
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-lg border border-line bg-elevated/40 p-3">
                <div className="text-ink-muted">Role / Status</div>
                <div className="mt-1 font-semibold text-ink uppercase">
                  {selectedDetail.role} • {selectedDetail.is_active ? 'Active' : 'Suspended'}
                </div>
              </div>
              <div className="rounded-lg border border-line bg-elevated/40 p-3">
                <div className="text-ink-muted">Two-Factor Auth</div>
                <div className="mt-1 font-semibold text-ink">
                  {selectedDetail.totp_enabled ? 'TOTP Enabled' : 'Disabled'}
                </div>
              </div>
              <div className="rounded-lg border border-line bg-elevated/40 p-3">
                <div className="text-ink-muted">Conversations / Messages</div>
                <div className="mt-1 font-semibold text-ink">
                  {selectedDetail.conversation_count} / {selectedDetail.message_count}
                </div>
              </div>
              <div className="rounded-lg border border-line bg-elevated/40 p-3">
                <div className="text-ink-muted">Documents / Memories</div>
                <div className="mt-1 font-semibold text-ink">
                  {selectedDetail.document_count} / {selectedDetail.memory_count}
                </div>
              </div>
              <div className="rounded-lg border border-line bg-elevated/40 p-3">
                <div className="text-ink-muted">AI Requests (OK / Fail)</div>
                <div className="mt-1 font-semibold text-ink">
                  {selectedDetail.ai_request_count} ({selectedDetail.successful_ai_requests} / {selectedDetail.failed_ai_requests})
                </div>
              </div>
              <div className="rounded-lg border border-line bg-elevated/40 p-3">
                <div className="text-ink-muted">Total Tokens</div>
                <div className="mt-1 font-semibold text-ink">
                  {selectedDetail.total_tokens !== null && selectedDetail.total_tokens !== undefined
                    ? selectedDetail.total_tokens.toLocaleString()
                    : 'Unavailable'}
                </div>
              </div>
            </div>

            <div>
              <div className="text-xs font-semibold text-ink mb-2">Recent Models Invoked</div>
              {selectedDetail.recent_ai_models.length === 0 ? (
                <p className="text-xs text-ink-muted">No AI invocations logged yet.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {selectedDetail.recent_ai_models.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-md border border-line bg-elevated px-2.5 py-1 font-mono text-[11px] text-ink"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
