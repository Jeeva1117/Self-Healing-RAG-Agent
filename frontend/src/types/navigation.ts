import type { LucideIcon } from 'lucide-react';

export interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  description: string;
  phase: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}
