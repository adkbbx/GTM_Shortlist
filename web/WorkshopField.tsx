import { useEffect, useRef, useState } from 'react';
import './WorkshopField.css';

const vertex = `attribute vec2 position; void main(){gl_Position=vec4(position,0.,1.);}`;
const fragment = `precision mediump float;
uniform vec2 resolution;
uniform float time;
void main(){
 vec2 uv=gl_FragCoord.xy/resolution;
 vec2 p=(uv-.5)*vec2(resolution.x/resolution.y,1.);
 float sweep=fract(time*.09)*1.6-.8;
 float beam=exp(-abs(p.y-sweep)*65.);
 float gridX=1.-smoothstep(.008,.018,abs(fract(p.x*10.+.5)-.5));
 float gridY=1.-smoothstep(.008,.018,abs(fract(p.y*10.+.5)-.5));
 float radius=length(p);
 float ring=1.-smoothstep(.001,.004,abs(radius-.29));
 float angle=atan(p.y,p.x);
 float trace=pow(max(0.,cos(angle-time*.35)),24.)*ring;
 float circuit=1.-smoothstep(.001,.005,abs(abs(p.x)-(.18+.08*sin(p.y*9.))));
 float light=beam*(.10+.55*max(gridX,gridY))+.8*trace+.3*circuit*beam;
 gl_FragColor=vec4(.72,.29,.08,clamp(light,0.,.8));
}`;

/** Decorative calibration plate. It never represents actual research progress. */
export function WorkshopField() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [paused, setPaused] = useState(false);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const surface = canvas.current;
    if (!surface) return;
    const gl = surface.getContext('webgl', { alpha: true, antialias: false, depth: false, premultipliedAlpha: false });
    if (!gl) return;
    const compile = (kind: number, source: string) => {
      const shader = gl.createShader(kind);
      if (!shader) return null;
      gl.shaderSource(shader, source); gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) { gl.deleteShader(shader); return null; }
      return shader;
    };
    const vs = compile(gl.VERTEX_SHADER, vertex), fs = compile(gl.FRAGMENT_SHADER, fragment);
    const program = gl.createProgram();
    if (!vs || !fs || !program) { if(vs) gl.deleteShader(vs); if(fs) gl.deleteShader(fs); if(program) gl.deleteProgram(program); return; }
    gl.attachShader(program, vs); gl.attachShader(program, fs); gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) { gl.deleteShader(vs); gl.deleteShader(fs); gl.deleteProgram(program); return; }
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
    gl.useProgram(program);
    const position = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const size = gl.getUniformLocation(program, 'resolution'), clock = gl.getUniformLocation(program, 'time');
    const preference = matchMedia('(prefers-reduced-motion: reduce)');
    let frame = 0, last = 0, elapsed = 0, inView = true, lost = false;
    const draw = () => {
      const rect = surface.getBoundingClientRect(), ratio = Math.min(devicePixelRatio || 1, 1.5);
      const width = Math.max(1, Math.round(rect.width*ratio)), height = Math.max(1, Math.round(rect.height*ratio));
      if (surface.width !== width || surface.height !== height) { surface.width=width; surface.height=height; }
      gl.viewport(0,0,width,height); gl.uniform2f(size,width,height); gl.uniform1f(clock,elapsed); gl.drawArrays(gl.TRIANGLES,0,6);
    };
    const tick = (now: number) => {
      if (now-last>=32) { elapsed += last ? Math.min((now-last)/1000,.1) : 0; last=now; draw(); }
      frame=requestAnimationFrame(tick);
    };
    const sync = () => {
      cancelAnimationFrame(frame); last=0;
      const playing = !paused && !preference.matches && !document.hidden && inView && !lost;
      surface.dataset.state=playing ? 'playing' : 'static';
      if (!lost) { draw(); if (playing) frame=requestAnimationFrame(tick); }
    };
    const observer = new IntersectionObserver(entries => { inView=entries.some(entry=>entry.isIntersecting); sync(); });
    const resize = new ResizeObserver(sync);
    const contextLost = () => { lost=true; setReady(false); sync(); };
    observer.observe(surface); resize.observe(surface);
    document.addEventListener('visibilitychange', sync); preference.addEventListener('change',sync);
    surface.addEventListener('webglcontextlost',contextLost);
    setReady(true); sync();
    return () => { cancelAnimationFrame(frame); observer.disconnect(); resize.disconnect(); document.removeEventListener('visibilitychange',sync); preference.removeEventListener('change',sync); surface.removeEventListener('webglcontextlost',contextLost); gl.deleteBuffer(buffer); gl.deleteProgram(program); gl.deleteShader(vs); gl.deleteShader(fs); };
  }, [paused]);
  return <div className="workshop-field" data-enhanced={ready}>
    <div className="workshop-plate" aria-hidden="true">
      <svg viewBox="0 0 320 250" fill="none"><path className="plate-grid" d="M0 50h320M0 100h320M0 150h320M0 200h320M60 0v250M110 0v250M160 0v250M210 0v250M260 0v250"/><path className="plate-frame" d="M20 35V20h15m250 0h15v15M20 215v15h15m250 0h15v-15M160 35v180M60 125h200"/><circle cx="160" cy="125" r="72"/><circle cx="160" cy="125" r="58" strokeDasharray="3 6"/><path d="M113 72 92 51H40m167 127 21 21h52M216 81h56M104 169H48"/><rect x="141" y="100" width="38" height="50" rx="2"/><path className="plate-accent" d="M150 112h20m-20 10h14m-14 10h20M160 48v10m0 134v10M83 125h10m134 0h10"/><circle className="plate-accent" cx="92" cy="51" r="3"/><circle className="plate-accent" cx="228" cy="199" r="3"/></svg>
      <canvas ref={canvas}/>
    </div>
    {ready && <button type="button" className="workshop-motion" aria-pressed={paused} onClick={()=>setPaused(value=>!value)}>{paused ? 'Play visual' : 'Pause visual'}</button>}
  </div>;
}
