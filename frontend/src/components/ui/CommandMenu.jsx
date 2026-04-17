import React, { useEffect, useState } from 'react';
import { Command } from 'cmdk';
import { Search, Compass, Book, ShieldAlert, Cpu } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function CommandMenu() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  // Toggle the menu when ⌘K is pressed
  useEffect(() => {
    const down = (e) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-start justify-center pt-[15vh]">
      <div className="w-[600px] max-w-full bg-[#18181b] border border-white/[0.08] shadow-2xl rounded-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <Command label="Global Command Menu"
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                e.preventDefault()
                setOpen(false)
              }
            }}
        >
          <div className="flex items-center border-b border-white/[0.08] px-4">
             <Search className="w-5 h-5 text-zinc-500 mr-2" />
             <Command.Input 
                autoFocus 
                placeholder="Search tools, investigate targets, or read docs..." 
                className="w-full bg-transparent outline-none h-14 text-white text-[15px] placeholder:text-zinc-500"
             />
             <kbd className="hidden sm:inline-flex items-center gap-1 bg-zinc-800 text-zinc-400 px-2 pl-3 py-1 rounded text-xs">
                ESC
             </kbd>
          </div>

          <Command.List className="max-h-[350px] overflow-y-auto p-2 scrollbar-hide text-[14px]">
            <Command.Empty className="py-6 text-center text-zinc-500 text-sm">No results found.</Command.Empty>

            <Command.Group heading="Investigations" className="text-xs font-medium text-zinc-500 px-2 py-2">
              <Command.Item 
                 onSelect={() => { setOpen(false); navigate('/topology'); }}
                 className="flex items-center gap-3 px-3 py-2.5 mt-1 rounded-lg text-zinc-300 hover:bg-white/[0.06] hover:text-white cursor-pointer aria-selected:bg-white/[0.06] aria-selected:text-white"
              >
                <Compass className="w-4 h-4 text-indigo-400" /> Open Topology Matrix
              </Command.Item>
              <Command.Item 
                 onSelect={() => { setOpen(false); navigate('/ai-analyst'); }}
                 className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-zinc-300 hover:bg-white/[0.06] hover:text-white cursor-pointer aria-selected:bg-white/[0.06] aria-selected:text-white"
              >
                <Cpu className="w-4 h-4 text-emerald-400" /> Consult AI Co-Analyst
              </Command.Item>
            </Command.Group>

            <Command.Group heading="Documentation & Protocol" className="text-xs font-medium text-zinc-500 px-2 py-2 mt-2">
              <Command.Item 
                 onSelect={() => { setOpen(false); navigate('/docs'); }}
                 className="flex items-center gap-3 px-3 py-2.5 mt-1 rounded-lg text-zinc-300 hover:bg-white/[0.06] hover:text-white cursor-pointer aria-selected:bg-white/[0.06] aria-selected:text-white"
              >
                <Book className="w-4 h-4 text-blue-400" /> Security Operations Manual (SOP)
              </Command.Item>
              <Command.Item 
                 onSelect={() => { setOpen(false); navigate('/audit'); }}
                 className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-zinc-300 hover:bg-white/[0.06] hover:text-white cursor-pointer aria-selected:bg-white/[0.06] aria-selected:text-white"
              >
                <ShieldAlert className="w-4 h-4 text-red-400" /> View Audit Logs Timeline
              </Command.Item>
            </Command.Group>
            
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
