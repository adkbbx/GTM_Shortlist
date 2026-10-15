/** An illustration of the current operation, never a timer or completion estimate. */
export function ResearchActivity({ stage, mode }: { stage: number; mode: 'working' | 'waiting' | 'still' }) {
  const mapping = stage === 1 || stage === 3;
  return <div className="research-visual" data-mode={mode} data-scene={mapping ? 'mapping' : 'reading'} aria-hidden="true">
    <svg viewBox="0 0 480 150" fill="none">
      <path className="research-connector" d="M91 75h109m80 0h109" />
      <path className="research-flow" d="M91 75h109m80 0h109" />
      <g className="research-source">
        <path className="research-paper-back" d="M38 33h42l14 14v68H38V33Z" />
        <path className="research-paper-face" d="M28 25h42l14 14v68H28V25Z" />
        <path className="research-paper-fold" d="M70 25v15h14M40 53h31M40 63h25M40 73h31M40 83h19" />
      </g>
      {mapping ? <g className="research-map">
        <path className="research-map-links" d="m215 44 50 8-38 48 44 9m-56-65 12 56m38-48 6 57" />
        {[[215, 44], [265, 52], [227, 100], [271, 109]].map(([x, y], index) =>
          <g className="research-map-node" key={index} style={{ animationDelay: `${index * 140}ms` }}>
            <rect x={x - 12} y={y - 12} width="24" height="24" rx="5" />
            <path d={`M${x - 5} ${y + 5}v-9h10v9m-6-6h2m-2 3h2`} />
          </g>)}
      </g> : <g className="research-reader">
        <rect className="research-reader-page" x="214" y="39" width="52" height="70" rx="5" />
        <path className="research-reader-lines" d="M224 54h32m-32 11h25m-25 11h32m-32 11h20" />
        <path className="research-read-beam" d="M207 54h66" />
      </g>}
      <g className="research-output">
        <rect className="research-paper-back" x="398" y="43" width="52" height="66" rx="4" />
        <rect className="research-paper-face" x="388" y="33" width="52" height="66" rx="4" />
        <path className="research-paper-fold" d="M400 48h28m-28 11h19m-19 15h28m-28 11h24" />
        <path className="research-evidence-mark" d="M400 71h28" />
      </g>
      {mode === 'waiting' && <g className="research-waiting">
        <circle cx="240" cy="75" r="28" />
        <path d="M240 58v18l10 7" />
      </g>}
    </svg>
    <div className="research-visual-labels"><span>Sources</span><span>{mode === 'waiting' ? 'Waiting to continue' : mapping ? 'Company research' : 'Source analysis'}</span><span>Research sheet</span></div>
  </div>;
}
