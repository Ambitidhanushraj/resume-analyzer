import { useState } from 'react';
import ResumeUpload from './components/ResumeUpload';
import AnalysisResults from './components/AnalysisResults';
import './styles.css';
function App() {
  const [results, setResults] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState('');
  const reset = () => { setResults(null); setError(''); };
  return <main className="app-shell"><nav className="topbar"><a className="brand" href="/" onClick={(e) => { e.preventDefault(); reset(); }}><span className="brand-mark">R</span><span>resume<span className="brand-accent">wise</span></span></a><span className="nav-label">AI RESUME INTELLIGENCE</span>{results && <button className="text-button" onClick={reset}>Analyze another</button>}</nav>{!results ? <><section className="hero"><p className="eyebrow">YOUR CAREER, CLEARER</p><h1>See what your resume<br /><em>is really saying.</em></h1><p className="hero-copy">Get instant clarity on your strengths, gaps, and the roles where you’ll make the strongest first impression.</p></section><section className="workspace"><ResumeUpload onAnalysisComplete={setResults} onError={setError} setLoading={setLoading} loading={loading} error={error} /></section><section className="how-it-works"><p className="eyebrow">HOW IT WORKS</p><div className="steps"><div><b>01</b><span>Upload your PDF</span></div><div><b>02</b><span>We read the details</span></div><div><b>03</b><span>Discover your fit</span></div></div></section></> : <AnalysisResults results={results} onReset={reset} />}</main>;
}
export default App;
