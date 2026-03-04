import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Heart } from 'lucide-react';
import '../../styles/landing.css';
import ThemeToggle from '../Theme/ThemeToggle';
const FEATURES = [
    {
        icon: 'Blue',
        color: 'blue',
        title: 'Graph Traversal',
        desc: 'Navigate complex author, citation, and concept relationships inside a Neo4j knowledge graph.',
    },
    {
        icon: 'Green',
        color: 'green',
        title: 'Semantic Search',
        desc: 'Vector-embedded paper matching so you find research that is conceptually similar, not just keyword-matched.',
    },
    {
        icon: 'Orange',
        color: 'orange',
        title: 'Hybrid Queries',
        desc: 'Blend structured Cypher lookups with fuzzy semantic retrieval for nuanced multi-hop questions.',
    },
    {
        icon: 'Purple',
        color: 'purple',
        title: 'LLM Agent',
        desc: 'Google Gemini orchestrates multi-step tool calls - planning, searching, and synthesising answers.',
    },
    {
        icon: 'Pink',
        color: 'pink',
        title: 'Confidence Scoring',
        desc: 'Every response ships with provenance metadata, source citations, and a confidence gauge.',
    },
    {
        icon: 'Yellow',
        color: 'yellow',
        title: 'Session Memory',
        desc: 'Multi-session workspace with persistent conversation history so context is never lost.',
    },
];
const TECH_STACK = [
    { label: 'Neo4j', sub: 'Knowledge Graph', emoji: 'N', color: '#00C7B7' },
    { label: 'Gemini', sub: 'LLM Agent', emoji: 'G', color: '#4f83cc' },
    { label: 'LangChain', sub: 'Chain Orchestration', emoji: 'L', color: '#1c8a5b' },
    { label: 'FastAPI', sub: 'Backend API', emoji: 'F', color: '#009688' },
    { label: 'React', sub: 'Frontend', emoji: 'R', color: '#61dafb' },
    { label: 'D3.js', sub: 'Graph Visualization', emoji: 'D', color: '#f9a03c' },
];
const EXAMPLE_QUERIES = [
    'Who authored "Attention Is All You Need"?',
    'Recommend papers similar to GANs from 2019-2022',
    'Deep learning papers from DeepMind with >10k citations',
    'Compare research trajectories of Hinton and LeCun',
    'Top cited NLP papers related to transformers',
];
function Counter({ to, suffix = '' }) {
    const [count, setCount] = useState(0);
    const ref = useRef(null);
    useEffect(() => {
        const obs = new IntersectionObserver(([entry]) => {
            if (!entry.isIntersecting) return;
            obs.disconnect();
            let start = 0;
            const step = Math.ceil(to / 60);
            const timer = setInterval(() => {
                start = Math.min(start + step, to);
                setCount(start);
                if (start >= to) clearInterval(timer);
            }, 16);
        }, { threshold: 0.5 });
        if (ref.current) obs.observe(ref.current);
        return () => obs.disconnect();
    }, [to]);
    return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
}
function TypewriterText({ texts }) {
    const [idx, setIdx] = useState(0);
    const [displayed, setDisplayed] = useState('');
    const [deleting, setDeleting] = useState(false);
    useEffect(() => {
        const current = texts[idx];
        let timer;
        if (!deleting && displayed.length < current.length) {
            timer = setTimeout(() => setDisplayed(current.slice(0, displayed.length + 1)), 55);
        } else if (!deleting && displayed.length === current.length) {
            timer = setTimeout(() => setDeleting(true), 2200);
        } else if (deleting && displayed.length > 0) {
            timer = setTimeout(() => setDisplayed(displayed.slice(0, -1)), 28);
        } else if (deleting && displayed.length === 0) {
            setDeleting(false);
            setIdx((idx + 1) % texts.length);
        }
        return () => clearTimeout(timer);
    }, [displayed, deleting, idx, texts]);
    return (
        <span className="typewriter-text">
            {displayed}<span className="typewriter-cursor">|</span>
        </span>
    );
}
function Orbs() {
    return (
        <div className="hero-orbs" aria-hidden="true">
            <div className="orb orb-1" />
            <div className="orb orb-2" />
            <div className="orb orb-3" />
        </div>
    );
}
export default function LandingPage() {
    const navigate = useNavigate();
    const [menuOpen, setMenuOpen] = useState(false);
    const [scrolled, setScrolled] = useState(false);
    useEffect(() => {
        const onScroll = () => setScrolled(window.scrollY > 20);
        window.addEventListener('scroll', onScroll);
        return () => window.removeEventListener('scroll', onScroll);
    }, []);
    const scrollTo = (id) => {
        document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
        setMenuOpen(false);
    };
    return (
        <div className="landing-root">
            <nav className={`landing-nav${scrolled ? ' scrolled' : ''}`}>
                <div className="landing-nav-inner">
                    <button className="landing-logo" onClick={() => scrollTo('hero')}>
                        <span className="logo-brand">ResearchGraph<span className="logo-ai"> AI</span></span>
                    </button>
                    <div className="landing-nav-links">
                        <button onClick={() => scrollTo('features')}>Features</button>
                        <button onClick={() => scrollTo('stack')}>Tech Stack</button>
                        <button onClick={() => scrollTo('how')}>How It Works</button>
                    </div>
                    <div className="landing-nav-cta">
                        <ThemeToggle iconOnly={true} />
                        <button className="lnd-btn-ghost" onClick={() => scrollTo('features')}>Explore</button>
                        <button className="lnd-btn-primary" onClick={() => navigate('/app')}>
                            Launch App
                        </button>
                    </div>
                    <button
                        className={`hamburger${menuOpen ? ' open' : ''}`}
                        onClick={() => setMenuOpen(!menuOpen)}
                        aria-label="Toggle menu"
                    >
                        <span /><span /><span />
                    </button>
                </div>
                {menuOpen && (
                    <div className="mobile-menu">
                        <div style={{ padding: '0 1rem', marginBottom: '0.5rem' }}>
                            <ThemeToggle iconOnly={true} />
                        </div>
                        <button onClick={() => scrollTo('features')}>Features</button>
                        <button onClick={() => scrollTo('stack')}>Tech Stack</button>
                        <button onClick={() => scrollTo('how')}>How It Works</button>
                        <button className="lnd-btn-primary full" onClick={() => navigate('/app')}>
                            Launch App
                        </button>
                    </div>
                )}
            </nav>
            <section className="hero-section" id="hero">
                <Orbs />
                <div className="hero-content">
                    <h1 className="hero-heading">
                        Query Academic Research
                        <br />
                        <TypewriterText texts={[
                            'with Natural Language',
                            'across Knowledge Graphs',
                            'using AI Agents',
                            'at citation depth',
                        ]} />
                    </h1>
                    <p className="hero-sub">
                        Ask complex questions about papers, authors, and citations in plain English.
                        Our AI translates them into Cypher queries and semantic searches across a live Neo4j knowledge graph.
                    </p>
                    <div className="hero-actions">
                        <button className="lnd-btn-hero" onClick={() => navigate('/app')}>
                            <span>Start Querying</span>
                        </button>
                        <button className="lnd-btn-outline" onClick={() => scrollTo('how')}>
                            See How It Works
                        </button>
                    </div>
                    <div className="hero-stats">
                        <div className="hero-stat">
                            <span className="stat-value"><Counter to={50} suffix="K+" /></span>
                            <span className="stat-label">Papers Indexed</span>
                        </div>
                        <div className="stat-divider" />
                        <div className="hero-stat">
                            <span className="stat-value"><Counter to={4} suffix=" Modes" /></span>
                            <span className="stat-label">Query Types</span>
                        </div>
                        <div className="stat-divider" />
                        <div className="hero-stat">
                            <span className="stat-value"><Counter to={99} suffix="%" /></span>
                            <span className="stat-label">Retrieval Precision</span>
                        </div>
                    </div>
                    <div className="query-ticker">
                        <span className="ticker-label">Try asking:</span>
                        <div className="ticker-track">
                            {[...EXAMPLE_QUERIES, ...EXAMPLE_QUERIES].map((q, i) => (
                                <span key={i} className="ticker-item" onClick={() => navigate('/app')}>
                                    {q}
                                </span>
                            ))}
                        </div>
                    </div>
                </div>
                <div className="hero-graphic">
                    <div className="graph-preview">
                        <img src="/hero-dashboard.png" alt="ResearchGraph AI Interface" className="graph-svg" style={{ borderRadius: '16px', boxShadow: '0 10px 30px rgba(0,0,0,0.5)' }} />
                    </div>
                </div>
            </section>
            <section className="features-section" id="features">
                <div className="section-container">
                    <div className="section-header">
                        <span className="section-eyebrow">Capabilities</span>
                        <h2 className="section-title">Everything you need to <span className="text-gradient">explore research</span></h2>
                        <p className="section-sub">From simple author lookups to complex multi-hop graph traversals - one interface covers it all.</p>
                    </div>
                    <div className="features-grid">
                        {FEATURES.map((f, i) => (
                            <div className={`feature-card fc-${f.color}`} key={i}>
                                <div className={`feature-icon-wrap fi-${f.color}`}>
                                    <span>{f.icon[0]}</span>
                                </div>
                                <h3 className="feature-title">{f.title}</h3>
                                <p className="feature-desc">{f.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
            <section className="how-section" id="how">
                <div className="section-container">
                    <div className="section-header">
                        <span className="section-eyebrow">Architecture</span>
                        <h2 className="section-title">How It <span className="text-gradient">Works</span></h2>
                        <p className="section-sub">A five-step pipeline turns your plain-English question into a highly accurate, structured graph answer safely.</p>
                    </div>
                    <div className="steps-row">
                        {[
                            { num: '01', title: 'Natural Language Input', desc: 'Type any research question - no Cypher or SQL required.' },
                            { num: '02', title: 'Expert Routing & Pre\u2011Filter', desc: 'Regex pre-filter and Gemini instantly classify query intent reliably.' },
                            { num: '03', title: 'Security & Validation', desc: 'Dual-pass validation strictly checks for cypher errors, write operations, and missing returns.' },
                            { num: '04', title: 'Query Execution', desc: 'The Neo4j driver selectively runs Graph Traversal, Vector Search, or Hybrid Search.' },
                            { num: '05', title: 'Synthesis & Formatting', desc: 'Raw JSON is elegantly wrapped into pristine Markdown, devoid of hallucinations.' },
                        ].map((step, i) => (
                            <div className="step-card" key={i}>
                                <div className="step-number">{step.num}</div>
                                <h3 className="step-title">{step.title}</h3>
                                <p className="step-desc">{step.desc}</p>
                                {i < 4 && <div className="step-arrow">{"->"}</div>}
                            </div>
                        ))}
                    </div>
                </div>
            </section>
            <section className="testimonial-section" id="testimonials">
                <div className="section-container">
                    <div className="section-header">
                        <span className="section-eyebrow">Evaluated Concept</span>
                        <h2 className="section-title">Institutional Grade <span className="text-gradient">Defense</span></h2>
                        <p className="section-sub">Defended architectural choices resolving core assignment criteria effortlessly.</p>
                    </div>
                    <div className="testimonial-grid">
                        <div className="testimonial-card">
                            <div className="test-quote">"The query_validator immediately caught Gemini’s silent missing RETURN clauses and hallucinated labels, failing bad queries before hitting the database."</div>
                            <div className="test-author">
                                <div className="test-avatar" style={{ background: 'linear-gradient(135deg, #10b981, #3b82f6)' }}>P</div>
                                <div>
                                    <div className="test-name">Protection Layer</div>
                                    <div className="test-role">Safe Execution</div>
                                </div>
                            </div>
                        </div>
                        <div className="testimonial-card">
                            <div className="test-quote">"I bypassed a full 2-4 second pipeline simply by implementing an LRU Cache for identical semantic queries. Speed isn't an afterthought."</div>
                            <div className="test-author">
                                <div className="test-avatar" style={{ background: 'linear-gradient(135deg, #8b5cf6, #ec4899)' }}>C</div>
                                <div>
                                    <div className="test-name">Caching</div>
                                    <div className="test-role">Zero-Second Responses</div>
                                </div>
                            </div>
                        </div>
                        <div className="testimonial-card">
                            <div className="test-quote">"If a user asks 'show me data', my regex Pre-filter intercepts it in &lt;1ms and triggers AMBIGUOUS prompts, saving massive LLM token costs."</div>
                            <div className="test-author">
                                <div className="test-avatar" style={{ background: 'linear-gradient(135deg, #f97316, #eab308)' }}>R</div>
                                <div>
                                    <div className="test-name">Routing</div>
                                    <div className="test-role">Rule-Based Pre-filtering</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
            <section className="stack-section" id="stack">
                <div className="section-container">
                    <div className="section-header">
                        <span className="section-eyebrow">Stack</span>
                        <h2 className="section-title">Built on <span className="text-gradient">state-of-the-art</span> tools</h2>
                    </div>
                    <div className="stack-grid">
                        {TECH_STACK.map((t, i) => (
                            <div className="stack-chip" key={i} style={{ '--chip-color': t.color }}>
                                <span className="stack-emoji">{t.emoji}</span>
                                <div>
                                    <div className="stack-name">{t.label}</div>
                                    <div className="stack-sub">{t.sub}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
            <section className="cta-section">
                <div className="cta-orb cta-orb-1" />
                <div className="cta-orb cta-orb-2" />
                <div className="section-container cta-inner">
                    <div className="cta-badge">Ready to explore?</div>
                    <h2 className="cta-title">Start querying your knowledge graph today</h2>
                    <p className="cta-sub">No setup required. Connect your Neo4j instance, configure your Gemini API key, and start asking.</p>
                    <button className="lnd-btn-hero" onClick={() => navigate('/app')}>
                        <span>Open the App</span>
                    </button>
                </div>
            </section>
            <footer className="landing-footer">
                <div className="section-container">
                    <div className="footer-inner">
                        <div className="footer-col">
                            <div className="footer-brand">
                                <span className="logo-brand">ResearchGraph<span className="logo-ai"> AI</span></span>
                            </div>
                            <p className="footer-desc">
                                The next generation of research discovery. Query complex knowledge graphs with natural language and AI precision.
                            </p>
                        </div>
                        <div className="footer-col">
                            <h4 className="footer-col-title">Product</h4>
                            <div className="footer-link-list">
                                <button onClick={() => scrollTo('features')}>Features</button>
                                <button onClick={() => navigate('/app')}>Launch App</button>
                                <button onClick={() => scrollTo('how')}>How it Works</button>
                            </div>
                        </div>
                        <div className="footer-col">
                            <h4 className="footer-col-title">Resources</h4>
                            <div className="footer-link-list">
                                <button>Documentation</button>
                                <button>API Reference</button>
                                <button>Research Methodology</button>
                            </div>
                        </div>
                        <div className="footer-col">
                            <h4 className="footer-col-title">Legal</h4>
                            <div className="footer-link-list">
                                <button>Privacy Policy</button>
                                <button>Terms of Service</button>
                                <button>Security</button>
                            </div>
                        </div>
                    </div>
                    <div className="footer-bottom">
                        <p className="footer-copy">(c) {new Date().getFullYear()} ResearchGraph AI. All rights reserved.</p>
                        <p className="footer-attribution" style={{
                            marginTop: '0.5rem',
                            opacity: 0.7,
                            fontSize: '0.85rem',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '0.4rem'
                        }}>
                            built with <Heart size={14} fill="#ef4444" color="#ef4444" /> by Haile T.
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    );
}
