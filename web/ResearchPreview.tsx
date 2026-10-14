import { useState } from 'react';

export function ResearchPreview() {
  const [detail, setDetail] = useState<'evidence' | 'unknowns'>('evidence');
  return <aside className="research-preview" aria-labelledby="preview-heading">
    <div className="preview-heading"><span className="preview-symbol" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M5 5h14v14H5zM8 9h8M8 12h8M8 15h5" stroke="currentColor" strokeWidth="1.5" /></svg></span><h2 id="preview-heading">A closer look, before outreach.</h2></div>
    <p>Up to three companies. A research sheet for each. You decide which ones deserve a conversation.</p>
    <div className="preview-selector" aria-label="Explore the research sheet">
      <button type="button" className="secondary" aria-pressed={detail === 'evidence'} onClick={() => setDetail('evidence')}>Evidence</button>
      <button type="button" className="secondary" aria-pressed={detail === 'unknowns'} onClick={() => setDetail('unknowns')}>Unknowns</button>
    </div>
    <div className="preview-content" aria-live="polite">
      {detail === 'evidence' ? <><h3>Every assessment has a trail.</h3><ol className="evidence-trail"><li><span>01</span><div><strong>Your fit criterion</strong><p>The requirement you confirmed.</p></div></li><li><span>02</span><div><strong>The source passage</strong><p>Exact words, with a link and retrieval date.</p></div></li><li><span>03</span><div><strong>Your decision</strong><p>Accept, reject, or leave it open.</p></div></li></ol></> : <><h3>Missing evidence stays visible.</h3><p className="preview-explanation">Ownership, stage, or product details may be unclear. An unknown stays a question to verify. Hypotheses are labelled separately from observed facts.</p><div className="preview-unknown"><span className="finding-status unknown">Unknown</span><p>A research outcome, never a guessed answer.</p></div></>}
    </div>
    <p className="preview-footnote">A guide to the output, not a company result.</p>
  </aside>;
}
