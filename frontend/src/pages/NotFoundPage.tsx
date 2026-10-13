import { Link } from 'react-router-dom';
import { Compass, LayoutDashboard, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export function NotFoundPage() {
  return (
    <div className="flex min-h-[70vh] items-center justify-center p-4">
      <Card className="max-w-md w-full text-center p-8 border-dashed border-slate-800 bg-slate-900/40">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 mx-auto mb-4">
          <Compass className="h-7 w-7" />
        </div>

        <div className="text-3xl font-extrabold tracking-tight text-slate-100 light:text-slate-900 font-mono">
          404
        </div>
        <h2 className="text-base font-semibold text-slate-200 light:text-slate-800 mt-1">
          Endpoint or Page Not Found
        </h2>
        <p className="text-xs text-slate-400 light:text-slate-500 mt-2 leading-relaxed">
          The requested resource is not mapped in the current Self-Healing RAG platform routing graph.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-2.5 mt-6">
          <Link to="/dashboard" className="w-full sm:w-auto">
            <Button size="sm" className="w-full gap-2 text-xs">
              <LayoutDashboard className="h-3.5 w-3.5" />
              <span>Back to Dashboard</span>
            </Button>
          </Link>
          <Link to="/search" className="w-full sm:w-auto">
            <Button variant="outline" size="sm" className="w-full gap-2 text-xs">
              <Search className="h-3.5 w-3.5" />
              <span>Search Playground</span>
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
