/* Cloudflare Turnstile, loaded only when a visitor starts a draft before signup. It stays invisible unless Cloudflare
   needs the visitor to interact, and the server verifies the token before any model call. */
type Widget = {
  render(host: HTMLElement, options: { sitekey: string; appearance: 'interaction-only'; action: string;
    callback: (token: string) => void; 'error-callback': () => void; 'expired-callback': () => void }): string;
  remove(id: string): void;
};
declare global { interface Window { turnstile?: Widget } }

const source = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
let loading: Promise<Widget> | null = null;

function load(): Promise<Widget> {
  loading ??= new Promise<Widget>((resolve, reject) => {
    if (window.turnstile) { resolve(window.turnstile); return; }
    const script = document.createElement('script');
    script.src = source; script.async = true;
    script.onload = () => window.turnstile ? resolve(window.turnstile) : reject(new Error('The browser check could not start.'));
    script.onerror = () => { loading = null; script.remove(); reject(new Error('The browser check could not load. Check your connection and try again.')); };
    document.head.append(script);
  });
  return loading;
}

/** A single-use token for the draft request, from a widget rendered into `host`. */
export async function turnstileToken(siteKey: string, host: HTMLElement): Promise<string> {
  const widget = await load();
  return new Promise<string>((resolve, reject) => {
    let id = '';
    const done = () => window.setTimeout(() => { if (id) widget.remove(id); });
    id = widget.render(host, { sitekey: siteKey, appearance: 'interaction-only', action: 'draft',
      callback: token => { done(); resolve(token); },
      'error-callback': () => { done(); reject(new Error('The browser check did not pass. Reload the page and try again.')); },
      'expired-callback': () => { done(); reject(new Error('The browser check expired. Try again.')); } });
  });
}
