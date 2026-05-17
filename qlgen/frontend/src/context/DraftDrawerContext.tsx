import React, { createContext, useContext, useState, useCallback } from 'react';
import type { DraftFormat, DraftTone } from '../types';

export interface DraftDrawerOptions {
  companyKbId: string;
  companyName?: string;
  domain?: string;
  signalId?: string;
  signalTitle?: string;
  signalType?: string;
  contactName?: string;
  contactTitle?: string;
  format?: DraftFormat;
  tone?: DraftTone;
}

interface DraftDrawerContextValue {
  isOpen: boolean;
  options: DraftDrawerOptions | null;
  openDraftDrawer: (opts: DraftDrawerOptions) => void;
  closeDraftDrawer: () => void;
}

const DraftDrawerContext = createContext<DraftDrawerContextValue>({
  isOpen: false,
  options: null,
  openDraftDrawer: () => {},
  closeDraftDrawer: () => {},
});

export const useDraftDrawer = () => useContext(DraftDrawerContext);

export const DraftDrawerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState<DraftDrawerOptions | null>(null);

  const openDraftDrawer = useCallback((opts: DraftDrawerOptions) => {
    setOptions(opts);
    setIsOpen(true);
  }, []);

  const closeDraftDrawer = useCallback(() => {
    setIsOpen(false);
    // Keep options briefly for exit animation, clear after
    setTimeout(() => setOptions(null), 300);
  }, []);

  return (
    <DraftDrawerContext.Provider value={{ isOpen, options, openDraftDrawer, closeDraftDrawer }}>
      {children}
    </DraftDrawerContext.Provider>
  );
};
