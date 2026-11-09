import React, { useState } from 'react';
import { X, Lock, Mail, User as UserIcon, AlertCircle, ArrowRight } from 'lucide-react';
import { loginUser, registerUser } from '../../services/api';
import { User } from '../../types';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: User, token: string) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        if (!username.trim() || username.length < 3) {
          throw new Error('Username must be at least 3 characters');
        }
        const data = await registerUser(username.trim(), email.trim(), password);
        onSuccess(data.user, data.access_token);
      } else {
        const data = await loginUser(email.trim(), password);
        onSuccess(data.user, data.access_token);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-charcoal-900 border border-charcoal-800 rounded-2xl shadow-2xl p-6 sm:p-8">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-charcoal-400 hover:text-white hover:bg-charcoal-800 transition-colors"
        >
          <X size={18} />
        </button>

        {/* Modal Header */}
        <div className="text-center mb-6">
          <div className="w-12 h-12 mx-auto rounded-xl bg-charcoal-800 border border-charcoal-700 p-2.5 mb-3 flex items-center justify-center">
            <img src="/logo.svg" alt="AUREVON" className="w-full h-full" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            {isRegister ? 'Create an Account' : 'Welcome to AUREVON'}
          </h2>
          <p className="text-xs text-charcoal-400 mt-1">
            {isRegister
              ? 'Join the independent, privacy-first AI platform'
              : 'Sign in to access your threads, preferences & memory'}
          </p>
        </div>

        {/* Error notification */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-2 text-rose-400 text-xs">
            <AlertCircle size={16} className="flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegister && (
            <div>
              <label className="block text-xs font-semibold text-charcoal-300 mb-1.5">Username</label>
              <div className="relative">
                <UserIcon size={15} className="absolute left-3 top-3 text-charcoal-500 pointer-events-none" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. archon_pilot"
                  className="w-full bg-charcoal-800 border border-charcoal-700 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-charcoal-500 focus:outline-none focus:border-brand-500 transition-colors"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-charcoal-300 mb-1.5">Email Address</label>
            <div className="relative">
              <Mail size={15} className="absolute left-3 top-3 text-charcoal-500 pointer-events-none" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@domain.com"
                className="w-full bg-charcoal-800 border border-charcoal-700 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-charcoal-500 focus:outline-none focus:border-brand-500 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-charcoal-300 mb-1.5">Password</label>
            <div className="relative">
              <Lock size={15} className="absolute left-3 top-3 text-charcoal-500 pointer-events-none" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full bg-charcoal-800 border border-charcoal-700 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-charcoal-500 focus:outline-none focus:border-brand-500 transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-brand-600/30 disabled:opacity-50"
          >
            <span>{loading ? 'Authenticating...' : isRegister ? 'Register Account' : 'Sign In'}</span>
            {!loading && <ArrowRight size={14} />}
          </button>
        </form>

        {/* Toggle Mode */}
        <div className="mt-6 text-center text-xs text-charcoal-400">
          <span>{isRegister ? 'Already have an account?' : "Don't have an account yet?"} </span>
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setError(null);
            }}
            className="text-brand-400 hover:text-brand-300 font-semibold underline underline-offset-2 ml-1"
          >
            {isRegister ? 'Sign In' : 'Create Account'}
          </button>
        </div>
      </div>
    </div>
  );
};
