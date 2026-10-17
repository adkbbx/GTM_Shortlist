import { PersonIcon } from './NavigationIcons';
import type { ReactNode } from 'react';
import type { Wallet } from './api';
import { CreditActivity } from './CreditActivity';
import './AccountTray.css';

export function AccountTray({ account, wallet, showActivity, onActivity, onClosed }: {
  account: ReactNode; wallet: Wallet | null; showActivity: boolean; onActivity: () => void; onClosed?: () => void;
}) {
  return <>
    <button type="button" className="account-trigger" popoverTarget="account-tray" aria-label="Open account tray" title="Account">
      <PersonIcon /><span>Account</span>
    </button>
    <div id="account-tray" className="account-tray" popover="auto" role="dialog" aria-labelledby="account-tray-title" onToggle={event => { if (event.newState === 'closed') onClosed?.(); }}>
      <div className="account-tray-heading"><h2 id="account-tray-title">Your account</h2><button type="button" popoverTarget="account-tray" popoverTargetAction="hide" aria-label="Close account tray">×</button></div>
      {account}
      {wallet?.mode === 'hosted' && <div className="tray-credits"><p className="wallet-balance">{wallet.available} {wallet.available === 1 ? 'credit' : 'credits'} available{wallet.reserved > 0 && <span>{wallet.reserved} reserved</span>}</p><button className="text-button" aria-expanded={showActivity} aria-controls="credit-activity" onClick={onActivity}>Credit activity</button></div>}
      {!wallet && <p className="hint">Loading credit balance…</p>}
      <div id="credit-activity" hidden={!showActivity}>{showActivity && wallet && <CreditActivity wallet={wallet} />}</div>
    </div>
  </>;
}
