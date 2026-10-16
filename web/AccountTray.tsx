import type { ReactNode } from 'react';
import type { Wallet } from './api';
import { CreditActivity } from './CreditActivity';
import './AccountTray.css';

export function AccountTray({ account, wallet, showActivity, onActivity }: {
  account: ReactNode; wallet: Wallet | null; showActivity: boolean; onActivity: () => void;
}) {
  return <>
    <button type="button" className="account-trigger" popoverTarget="account-tray" aria-label="Open account tray" title="Account">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="8" r="3.5"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/></svg><span>Account</span>
    </button>
    <div id="account-tray" className="account-tray" popover="auto" role="dialog" aria-labelledby="account-tray-title">
      <div className="account-tray-heading"><h2 id="account-tray-title">Your account</h2><button type="button" popoverTarget="account-tray" popoverTargetAction="hide" aria-label="Close account tray">×</button></div>
      {account}
      {wallet?.mode === 'hosted' && <div className="tray-credits"><p className="wallet-balance">{wallet.available} {wallet.available === 1 ? 'credit' : 'credits'} available{wallet.reserved > 0 && <span>{wallet.reserved} reserved</span>}</p><button className="text-button" aria-expanded={showActivity} aria-controls="credit-activity" onClick={onActivity}>Credit activity</button></div>}
      {!wallet && <p className="hint">Loading credit balance…</p>}
      <div id="credit-activity" hidden={!showActivity}>{showActivity && wallet && <CreditActivity wallet={wallet} />}</div>
    </div>
  </>;
}
