import { useState, useEffect, useRef } from "react";
import "./App.css";

interface Product {
  id: string;
  title: string;
  description: string;
  thumbnail?: string;
}

interface CartItem {
  product: Product;
  quantity: number;
}

interface Recommendation {
  title: string;
  description: string;
  product?: Product;
}

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

function App() {
  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [query, setQuery] = useState("");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [thinkingText, setThinkingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [phase, setPhase] = useState<"idle" | "thinking" | "responding" | "done">("idle");
  const [stats, setStats] = useState({ tokens: 0, elapsed: 0 });
  const [addedItems, setAddedItems] = useState<Set<string>>(new Set());
  const [backendError, setBackendError] = useState<string | null>(null);
  const phaseRef = useRef<"idle" | "thinking" | "responding" | "done">("idle");
  const startTime = useRef<number>(0);
  const thinkingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();

    const loadProducts = async () => {
      try {
        setBackendError(null);
        const response = await fetch(`${API_BASE}/products`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Products request failed (${response.status})`);
        }

        const data = await response.json();
        const products = data.products || [];
        setAllProducts(products);

        // Pre-load cart with 2 items for demo
        if (products.length >= 2) {
          setCart([
            { product: products[0], quantity: 1 },
            { product: products[1], quantity: 1 },
          ]);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        const message =
          error instanceof Error
            ? error.message
            : "Unable to connect to backend";
        setBackendError(`Backend unavailable: ${message}`);
      }
    };

    loadProducts();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (thinkingRef.current) {
      thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight;
    }
  }, [thinkingText]);

  const cartTotal = cart.reduce((sum, item) => sum + item.quantity * 2999, 0);
  const cartCount = cart.reduce((sum, item) => sum + item.quantity, 0);

  const updateQuantity = (productId: string, delta: number) => {
    setCart((prev) =>
      prev
        .map((item) =>
          item.product.id === productId
            ? { ...item, quantity: item.quantity + delta }
            : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  const addToCart = (product: Product) => {
    setAddedItems((prev) => new Set([...prev, product.id]));
    setCart((prev) => {
      const existing = prev.find((i) => i.product.id === product.id);
      if (existing) {
        return prev.map((i) =>
          i.product.id === product.id ? { ...i, quantity: i.quantity + 1 } : i
        );
      }
      return [...prev, { product, quantity: 1 }];
    });
    setTimeout(() => {
      setAddedItems((prev) => {
        const next = new Set(prev);
        next.delete(product.id);
        return next;
      });
    }, 1500);
  };

  const parseRecommendations = (text: string): Recommendation[] => {
  const recs: Recommendation[] = [];
  
  // Match numbered items: "1. **Product Name**" or "1. Product Name:"
  const numbered = [...text.matchAll(/\d+\.\s+\*?\*?([^*\n:]+)\*?\*?[:\s]/g)];
  
  for (const match of numbered) {
    const rawTitle = match[1].trim();
    // Skip if it looks like a heading not a product
    if (rawTitle.toLowerCase().includes("recommendation") || 
        rawTitle.toLowerCase().includes("why it") ||
        rawTitle.toLowerCase().includes("here's") ||
        rawTitle.length > 40) continue;

    const product = allProducts.find(
      (p) => p.title.toLowerCase().includes(rawTitle.toLowerCase()) ||
             rawTitle.toLowerCase().includes(p.title.toLowerCase().split(" ")[0])
    );

    const afterMatch = text.slice(match.index! + match[0].length, match.index! + match[0].length + 150);
    const desc = afterMatch.replace(/\*\*/g, "").split("\n")[0].trim();

    if (rawTitle) {
      recs.push({ 
        title: product?.title || rawTitle, 
        description: desc, 
        product 
      });
    }
  }
  return recs.slice(0, 4);
};

  const getPrice = (title: string): string => {
    const t = title.toLowerCase();
    if (t.includes("shoe") || t.includes("trainer")) return "£89.99";
    if (t.includes("jacket") || t.includes("hoodie")) return "£64.99";
    if (t.includes("backpack")) return "£49.99";
    if (t.includes("earbuds") || t.includes("wireless")) return "£44.99";
    if (t.includes("legging") || t.includes("tight")) return "£34.99";
    if (t.includes("mat")) return "£32.99";
    if (t.includes("roller")) return "£24.99";
    if (t.includes("bottle")) return "£19.99";
    if (t.includes("cap") || t.includes("hat")) return "£16.99";
    if (t.includes("band") || t.includes("resistance")) return "£14.99";
    if (t.includes("sock")) return "£12.99";
    return "£29.99";
  };

  const handleRecommend = async () => {
    if (!query.trim() || isStreaming) return;
    setBackendError(null);
    setRecommendations([]);
    setThinkingText("");
    setIsStreaming(true);
    setIsThinking(true);
    setPhase("thinking");
    phaseRef.current = "thinking";
    startTime.current = Date.now();
    let tokenCount = 0;
    let responseText = "";

    try {
      const res = await fetch(`${API_BASE}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_query: query }),
      });

      if (!res.ok) {
        throw new Error(`Recommend request failed (${res.status})`);
      }

      if (!res.body) {
        throw new Error("Streaming response is empty");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n").filter((l) => l.startsWith("data: "));

        for (const line of lines) {
          try {
            const json = JSON.parse(line.replace("data: ", ""));
            const thinkToken = json.thinking || "";
            const respToken = json.response || "";
            if (!thinkToken && !respToken) continue;
            tokenCount++;

            setStats({
              tokens: tokenCount,
              elapsed: Math.round((Date.now() - startTime.current) / 1000),
            });

            if (thinkToken) {
              setThinkingText((prev) => prev + thinkToken);
            }

            if (respToken) {
              if (phaseRef.current !== "responding") {
                phaseRef.current = "responding";
                setPhase("responding");
                setIsThinking(false);
              }
              responseText += respToken;
              const recs = parseRecommendations(responseText);
              if (recs.length > 0) setRecommendations(recs);
            }
          } catch {}
        }
      }
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unable to connect to backend";
      setBackendError(`Recommendation failed: ${message}`);
    } finally {
      setIsStreaming(false);
      setIsThinking(false);
      setPhase("done");
      phaseRef.current = "done";
    }
  };

  const handleReset = () => {
    setRecommendations([]);
    setThinkingText("");
    setQuery("");
    setPhase("idle");
    phaseRef.current = "idle";
    setIsStreaming(false);
    setIsThinking(false);
    setStats({ tokens: 0, elapsed: 0 });
  };

  return (
    <div className="app">
      {/* Nav */}
      <nav className="nav">
        <div className="nav-left">
          <div className="nav-logo">ActiveEdge</div>
          <span className="nav-tagline">Powered by Edge AI</span>
        </div>
        <div className="nav-right">
          <div className="nav-badge badge--online">
            <span className="dot" />
            ON-DEVICE
          </div>
          <div className="cart-icon">
            🛒
            {cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
          </div>
        </div>
      </nav>

      <main className="main">
        {/* Left: Cart */}
        <section className="cart-panel">
          <div className="panel-header">
            <h2 className="panel-title">Your Cart</h2>
            <span className="item-count">{cartCount} {cartCount === 1 ? "item" : "items"}</span>
          </div>

          <div className="cart-items">
            {cart.length === 0 ? (
              <div className="empty-cart">
                <p>🛒</p>
                <p>Your cart is empty</p>
              </div>
            ) : (
              cart.map((item) => (
                <div key={item.product.id} className="cart-item">
                  <div className="cart-item-thumb">
                    {item.product.thumbnail ? (
                      <img src={item.product.thumbnail} alt={item.product.title} />
                    ) : (
                      <div className="thumb-placeholder">
                        {item.product.title.charAt(0)}
                      </div>
                    )}
                  </div>
                  <div className="cart-item-info">
                    <p className="cart-item-title">{item.product.title}</p>
                    <p className="cart-item-price">{getPrice(item.product.title)}</p>
                  </div>
                  <div className="cart-item-controls">
                    <button className="qty-btn" onClick={() => updateQuantity(item.product.id, -1)}>−</button>
                    <span className="qty">{item.quantity}</span>
                    <button className="qty-btn" onClick={() => updateQuantity(item.product.id, 1)}>+</button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="cart-footer">
            <div className="cart-subtotal">
              <span>Subtotal</span>
              <span className="subtotal-amount">£{(cartTotal / 100).toFixed(2)}</span>
            </div>
            <button className="checkout-btn">Proceed to Checkout →</button>
            <p className="cart-note">Free delivery on orders over £50</p>
          </div>
        </section>

        {/* Right: AI Panel */}
        <section className="ai-panel">
          {/* Header */}
          <div className="ai-panel-header">
            <div className="ai-header-left">
              <div>
                <h2 className="ai-title">AI Shopping Assistant</h2>
                <p className="ai-subtitle">Powered by DeepSeek-R1 · On-Device · Zero Data Egress</p>
              </div>
            </div>
            {phase !== "idle" && (
              <div className="ai-header-right">
                <span className="stats-pill">
                  {stats.tokens} tokens · {stats.elapsed}s
                </span>
                <button className="reset-btn" onClick={handleReset}>↺ Reset</button>
              </div>
            )}
          </div>

          {/* Query */}
          <div className="query-section">
            <p className="query-label">What are you looking for today?</p>
            <div className="query-row">
              <input
                className="query-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. I want to start running outdoors..."
                onKeyDown={(e) => e.key === "Enter" && handleRecommend()}
                disabled={isStreaming}
              />
              <button
                className={`analyse-btn ${isStreaming ? "analyse-btn--busy" : ""}`}
                onClick={handleRecommend}
                disabled={isStreaming || !query.trim()}
              >
                {isStreaming ? (
                  <><span className="spinner" /> Thinking...</>
                ) : (
                  "Find Products →"
                )}
              </button>
            </div>
            {backendError && <p className="backend-error">{backendError}</p>}
          </div>

          {/* Thinking chain */}
          {(phase === "thinking" || phase === "responding" || phase === "done") && thinkingText && (
            <div className="thinking-section">
              <div className="thinking-header">
                <span className="thinking-label">
                  {isThinking && <span className="thinking-dot" />}
                  {isThinking ? "AI is reasoning..." : "Reasoning complete"}
                </span>
                <span className="thinking-chars">{thinkingText.length} chars</span>
              </div>
              <div className="thinking-box" ref={thinkingRef}>
                <pre className="thinking-text">
                  {thinkingText}
                  {isThinking && <span className="cursor">▋</span>}
                </pre>
              </div>
            </div>
          )}

          {/* Recommendations */}
          {recommendations.length > 0 && (
            <div className="recommendations-section">
              <div className="recs-header">
                <h3 className="recs-title">Recommended For You</h3>
                {phase === "done" && <span className="done-badge">✓ Complete</span>}
              </div>
              <div className="recs-grid">
                {recommendations.map((rec, i) => (
                  <div key={i} className="rec-card">
                    <div className="rec-thumb">
                      {rec.product?.thumbnail ? (
                        <img src={rec.product.thumbnail} alt={rec.title} />
                      ) : (
                        <div className="rec-thumb-placeholder">
                          {rec.title.charAt(0)}
                        </div>
                      )}
                    </div>
                    <div className="rec-info">
                      <p className="rec-title">{rec.title}</p>
                      <p className="rec-desc">{rec.description?.slice(0, 80)}...</p>
                      <div className="rec-footer">
                        <span className="rec-price">{getPrice(rec.title)}</span>
                        <button
                          className={`add-btn ${rec.product && addedItems.has(rec.product.id) ? "add-btn--added" : ""}`}
                          onClick={() => rec.product && addToCart(rec.product)}
                          disabled={!rec.product}
                        >
                          {rec.product && addedItems.has(rec.product.id) ? "✓ Added!" : "+ Add to Cart"}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Idle state */}
          {phase === "idle" && (
            <div className="idle-state">
              <div className="idle-suggestions">
                <p className="suggestions-label">Try asking:</p>
                {[
                  "I want to start running outdoors",
                  "I need gear for a home workout",
                  "Looking for a gift for a fitness lover",
                  "I want to recover faster after exercise",
                ].map((s) => (
                  <button
                    key={s}
                    className="suggestion-chip"
                    onClick={() => setQuery(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
              <div className="idle-features">
                <div className="feature">⚡ Streams token by token</div>
                <div className="feature">🔒 Zero data leaves device</div>
                <div className="feature">🧠 Full reasoning transparency</div>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;