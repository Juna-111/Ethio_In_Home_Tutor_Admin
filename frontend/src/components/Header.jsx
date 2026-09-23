import React from 'react';
import { BookOpen, User } from 'lucide-react';

export default function Header({ user }) {
  return (
    <header className="bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 text-white p-5 rounded-b-3xl shadow-lg mb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-11 h-11 bg-white/15 backdrop-blur-sm rounded-2xl flex items-center justify-center border border-white/20 shadow-inner">
            <BookOpen className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">MentorLink</h1>
            <p className="text-xs text-blue-100 font-medium">Ethiopian In-Home Tutoring</p>
          </div>
        </div>

        {user ? (
          <div className="flex items-center space-x-2 bg-white/10 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/15 text-xs font-medium">
            <User className="w-3.5 h-3.5 text-blue-200" />
            <span className="truncate max-w-[100px]">{user.first_name || user.username}</span>
          </div>
        ) : (
          <div className="bg-white/10 px-2.5 py-1 rounded-full text-[11px] text-blue-200 font-medium">
            Web Preview
          </div>
        )}
      </div>
    </header>
  );
}
