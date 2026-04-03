import { useEffect, useRef, useState } from "react";
import "./App.css";

interface ProductOptionValue {
  value: string;
}

interface ProductOption {
  title: string;
  values?: ProductOptionValue[];
}

interface CalculatedPrice {
  calculated_amount?: number;
  currency_code?: string;
}

interface ProductVariantOption {
  value: string;
  option?: {
    title: string;
  };
}

interface ProductVariant {
  id: string;
  title: string;
  calculated_price?: CalculatedPrice;
  options?: ProductVariantOption[];
}

interface Product {
  id: string;
  title: string;
  description: string;
  thumbnail?: string;
  options?: ProductOption[];
  variants?: ProductVariant[];
}

interface CartItem {
  product: Product;
  variantId?: string;
  quantity: number;
}

interface Recommendation {
  id: string;
  title: string;
  description: string;
  product?: Product;
}

type ParsedRecommendation = Recommendation | null;

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

function App() {
  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [query, setQuery] = useState("");
  const [recommendMode, setRecommendMode] = useState<"fast" | "deep">("fast");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [insightText, setInsightText] = useState("");
  const [traceSteps, setTraceSteps] = useState<string[]>([]);
  const [selectedVariants, setSelectedVariants] = useState<Record<string, string>>(
    {}
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [phase, setPhase] = useState<"idle" | "thinking" | "responding" | "done">(
    "idle"
  );
  const [stats, setStats] = useState({ tokens: 0, elapsed: 0 });
  const [addedItems, setAddedItems] = useState<Set<string>>(new Set());
  const [backendError, setBackendError] = useState<string | null>(null);
  const phaseRef = useRef<"idle" | "thinking" | "responding" | "done">("idle");
  const startTime = useRef<number>(0);

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
        setSelectedVariants(
          Object.fromEntries(
            products
              .map(
                (product: Product): [string, string | undefined] => [
                  product.id,
                  product.variants?.[0]?.id,
                ]
              )
              .filter(
                (entry: [string, string | undefined]): entry is [string, string] =>
                  Boolean(entry[1])
              )
          )
        );

        if (products.length >= 2) {
          setCart([
            {
              product: products[0],
              variantId: products[0].variants?.[0]?.id,
              quantity: 1,
            },
            {
              product: products[1],
              variantId: products[1].variants?.[0]?.id,
              quantity: 1,
            },
          ]);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        const message =
          error instanceof Error ? error.message : "Unable to connect to backend";
        setBackendError(`Backend unavailable: ${message}`);
      }
    };

    loadProducts();
    return () => controller.abort();
  }, []);

  const normalizeTitle = (value: string): string =>
    value
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

  const getVariantPrices = (product: Product): number[] =>
    (product.variants || [])
      .map((variant) => variant.calculated_price?.calculated_amount)
      .filter((amount): amount is number => typeof amount === "number");

  const getDefaultVariant = (product?: Product): ProductVariant | undefined =>
    product?.variants?.[0];

  const getSelectedVariant = (
    product?: Product,
    variantId?: string
  ): ProductVariant | undefined => {
    if (!product?.variants?.length) return undefined;

    return (
      product.variants.find((variant) => variant.id === variantId) ||
      getDefaultVariant(product)
    );
  };

  const getPrimaryCurrency = (product?: Product): string =>
    product?.variants?.find((variant) => variant.calculated_price?.currency_code)
      ?.calculated_price?.currency_code || "EUR";

  const formatCurrency = (amount: number, currencyCode: string): string =>
    new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: currencyCode.toUpperCase(),
    }).format(amount);

  const getPriceLabel = (product?: Product, variantId?: string): string => {
    if (!product) return "";

    const selectedVariant = getSelectedVariant(product, variantId);
    const selectedAmount = selectedVariant?.calculated_price?.calculated_amount;
    if (typeof selectedAmount === "number") {
      return formatCurrency(selectedAmount, getPrimaryCurrency(product));
    }

    const prices = getVariantPrices(product);
    if (!prices.length) return "";

    const currencyCode = getPrimaryCurrency(product);
    const min = Math.min(...prices);
    const max = Math.max(...prices);

    return min === max
      ? formatCurrency(min, currencyCode)
      : `From ${formatCurrency(min, currencyCode)}`;
  };

  const getOptionSummary = (product?: Product): string => {
    if (!product?.options?.length) return "";

    return product.options
      .map((option) => {
        const count = option.values?.length || 0;
        return count
          ? `${option.title}: ${count} option${count === 1 ? "" : "s"}`
          : option.title;
      })
      .join(" | ");
  };

  const getVariantLabel = (variant?: ProductVariant): string => {
    if (!variant) return "";

    if (variant.options?.length) {
      return variant.options
        .map((option) => `${option.option?.title || "Option"}: ${option.value}`)
        .join(" | ");
    }

    return variant.title;
  };

  const matchProductByTitle = (rawTitle: string): Product | undefined => {
    const normalizedRawTitle = normalizeTitle(rawTitle);
    if (!normalizedRawTitle) return undefined;

    const exactMatch = allProducts.find(
      (product) => normalizeTitle(product.title) === normalizedRawTitle
    );
    if (exactMatch) return exactMatch;

    return allProducts.find((product) => {
      const normalizedProductTitle = normalizeTitle(product.title);
      return (
        normalizedProductTitle.includes(normalizedRawTitle) ||
        normalizedRawTitle.includes(normalizedProductTitle)
      );
    });
  };

  const resolveRecommendationProduct = (
    recommendation: Recommendation
  ): Product | undefined =>
    recommendation.product ||
    allProducts.find((candidate) => candidate.id === recommendation.id) ||
    matchProductByTitle(recommendation.title);

  const cartTotal = cart.reduce((sum, item) => {
    const unitPrice =
      getSelectedVariant(item.product, item.variantId)?.calculated_price
        ?.calculated_amount || 0;
    return sum + item.quantity * unitPrice;
  }, 0);
  const cartCount = cart.reduce((sum, item) => sum + item.quantity, 0);

  const updateQuantity = (
    productId: string,
    variantId: string | undefined,
    delta: number
  ) => {
    setCart((prev) =>
      prev
        .map((item) =>
          item.product.id === productId && item.variantId === variantId
            ? { ...item, quantity: item.quantity + delta }
            : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  const addToCart = (product: Product) => {
    const variantId =
      selectedVariants[product.id] || getDefaultVariant(product)?.id;

    setAddedItems((prev) => new Set([...prev, product.id]));
    setCart((prev) => {
      const existing = prev.find(
        (item) => item.product.id === product.id && item.variantId === variantId
      );
      if (existing) {
        return prev.map((item) =>
          item.product.id === product.id && item.variantId === variantId
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }
      return [...prev, { product, variantId, quantity: 1 }];
    });

    setTimeout(() => {
      setAddedItems((prev) => {
        const next = new Set(prev);
        next.delete(product.id);
        return next;
      });
    }, 1500);
  };

  const extractJsonObject = (value: string): string | null => {
    const codeFenceMatch = value.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (codeFenceMatch) {
      return codeFenceMatch[1].trim();
    }

    const start = value.indexOf("{");
    const end = value.lastIndexOf("}");
    if (start === -1 || end === -1 || end <= start) return null;
    return value.slice(start, end + 1);
  };

  const parseRecommendations = (text: string): Recommendation[] => {
    const jsonText = extractJsonObject(text);
    if (!jsonText) return [];

    try {
      const parsed = JSON.parse(jsonText) as {
        recommendations?: Array<{
          id?: string;
          title?: string;
          reason?: string;
        }>;
      };

      const seenKeys = new Set<string>();

      const mappedRecommendations: ParsedRecommendation[] = (
        parsed.recommendations || []
      ).map((item) => {
          const product =
            allProducts.find((candidate) => candidate.id === item.id) ||
            (item.title ? matchProductByTitle(item.title) : undefined);
          const key = product?.id || item.id || normalizeTitle(item.title || "");

          if (!key || seenKeys.has(key)) {
            return null;
          }

          seenKeys.add(key);
          return {
            id: product?.id || item.id || key,
            title: product?.title || item.title || "Recommendation",
            description: item.reason || "",
            product,
          };
        });

      return mappedRecommendations
        .filter((item): item is Recommendation => item !== null)
        .slice(0, 4);
    } catch {
      return [];
    }
  };

  const visibleRecommendations = recommendations.filter((rec, index, list) => {
    const resolvedProduct = resolveRecommendationProduct(rec);
    const key = resolvedProduct?.id || rec.id || normalizeTitle(rec.title);
    return (
      list.findIndex(
        (item) =>
          (resolveRecommendationProduct(item)?.id ||
            item.id ||
            normalizeTitle(item.title)) === key
      ) === index
    );
  });

  const getProgressLabel = (): string => {
    if (phase === "thinking") {
      if (recommendMode === "deep") {
        return "Deep AI mode is reasoning locally with llama3.2:3b...";
      }
      return stats.elapsed >= 6
        ? "Matching your request to the best products..."
        : "Searching the catalogue...";
    }

    if (phase === "responding") {
      return visibleRecommendations.length > 0
        ? "Explaining these picks locally with llama3.2:3b..."
        : "Finalising recommendations...";
    }

    if (phase === "done" && visibleRecommendations.length > 0) {
      return insightText || traceSteps.length
        ? "Recommendations and AI insight ready."
        : "Recommendations ready.";
    }

    return "";
  };

  const handleRecommend = async () => {
    if (!query.trim() || isStreaming) return;

    setBackendError(null);
    setRecommendations([]);
    setInsightText("");
    setTraceSteps([]);
    setIsStreaming(true);
    setPhase("thinking");
    phaseRef.current = "thinking";
    startTime.current = Date.now();

    let tokenCount = 0;
    let responseText = "";

    try {
      const res = await fetch(`${API_BASE}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_query: query, mode: recommendMode }),
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
        const lines = chunk.split("\n").filter((line) => line.startsWith("data: "));

        for (const line of lines) {
          try {
            const json = JSON.parse(line.replace("data: ", ""));
            const respToken = json.response || "";
            const payloadType = json.type || "recommendations";
            if (!respToken && !json.done) continue;

            tokenCount++;
            setStats({
              tokens: tokenCount,
              elapsed: Math.round((Date.now() - startTime.current) / 1000),
            });

            if (payloadType === "recommendations" && respToken) {
              if (phaseRef.current !== "responding") {
                phaseRef.current = "responding";
                setPhase("responding");
              }

              responseText += respToken;
              const recs = parseRecommendations(responseText);
              if (recs.length > 0) {
                setRecommendations(recs);
              }
            } else if (payloadType === "insight" && respToken) {
              if (phaseRef.current !== "responding") {
                phaseRef.current = "responding";
                setPhase("responding");
              }

              setInsightText(respToken);
            } else if (payloadType === "trace" && Array.isArray(json.trace)) {
              setTraceSteps(
                json.trace.filter(
                  (item: unknown): item is string =>
                    typeof item === "string" && item.trim().length > 0
                )
              );
            } else if (payloadType === "done" && json.done) {
              setPhase("done");
              phaseRef.current = "done";
            }
          } catch {
            // Ignore incomplete JSON chunks while the stream is still assembling.
          }
        }
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to connect to backend";
      setBackendError(`Recommendation failed: ${message}`);
    } finally {
      setIsStreaming(false);
      setPhase("done");
      phaseRef.current = "done";
    }
  };

  const handleReset = () => {
    setRecommendations([]);
    setInsightText("");
    setTraceSteps([]);
    setQuery("");
    setPhase("idle");
    phaseRef.current = "idle";
    setIsStreaming(false);
    setStats({ tokens: 0, elapsed: 0 });
  };

  return (
    <div className="app">
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
            Cart
            {cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
          </div>
        </div>
      </nav>

      <main className="main">
        <section className="cart-panel">
          <div className="panel-header">
            <h2 className="panel-title">Your Cart</h2>
            <span className="item-count">
              {cartCount} {cartCount === 1 ? "item" : "items"}
            </span>
          </div>

          <div className="cart-items">
            {cart.length === 0 ? (
              <div className="empty-cart">
                <p>Cart</p>
                <p>Your cart is empty</p>
              </div>
            ) : (
              cart.map((item) => (
                <div
                  key={`${item.product.id}-${item.variantId || "default"}`}
                  className="cart-item"
                >
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
                    <p className="cart-item-price">
                      {getPriceLabel(item.product, item.variantId)}
                    </p>
                    {getVariantLabel(
                      getSelectedVariant(item.product, item.variantId)
                    ) && (
                      <p className="cart-item-meta">
                        {getVariantLabel(
                          getSelectedVariant(item.product, item.variantId)
                        )}
                      </p>
                    )}
                  </div>
                  <div className="cart-item-controls">
                    <button
                      className="qty-btn"
                      onClick={() =>
                        updateQuantity(item.product.id, item.variantId, -1)
                      }
                    >
                      -
                    </button>
                    <span className="qty">{item.quantity}</span>
                    <button
                      className="qty-btn"
                      onClick={() =>
                        updateQuantity(item.product.id, item.variantId, 1)
                      }
                    >
                      +
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="cart-footer">
            <div className="cart-subtotal">
              <span>Subtotal</span>
              <span className="subtotal-amount">
                {formatCurrency(cartTotal, getPrimaryCurrency(cart[0]?.product))}
              </span>
            </div>
            <button className="checkout-btn">Proceed to Checkout -&gt;</button>
            <p className="cart-note">Free delivery on orders over 50</p>
          </div>
        </section>

        <section className="ai-panel">
          <div className="ai-panel-header">
            <div className="ai-header-left">
              <div>
                <h2 className="ai-title">AI Shopping Assistant</h2>
                <p className="ai-subtitle">
                  {recommendMode === "fast"
                    ? "Matched locally | Explained locally by llama3.2:3b | Zero Data Egress"
                    : "Ranked locally by llama3.2:3b | Zero Data Egress"}
                </p>
              </div>
            </div>
            {phase !== "idle" && (
              <div className="ai-header-right">
                <span className="stats-pill">
                  {stats.tokens} tokens | {stats.elapsed}s
                </span>
                <button className="reset-btn" onClick={handleReset}>
                  Reset
                </button>
              </div>
            )}
          </div>

          <div className="query-section">
            <p className="query-label">What are you looking for today?</p>
            <div className="mode-toggle" role="tablist" aria-label="Recommendation mode">
              <button
                className={`mode-toggle-btn ${
                  recommendMode === "fast" ? "mode-toggle-btn--active" : ""
                }`}
                onClick={() => setRecommendMode("fast")}
                disabled={isStreaming}
              >
                Fast
              </button>
              <button
                className={`mode-toggle-btn ${
                  recommendMode === "deep" ? "mode-toggle-btn--active" : ""
                }`}
                onClick={() => setRecommendMode("deep")}
                disabled={isStreaming}
              >
                Deep AI
              </button>
            </div>
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
                  <>
                    <span className="spinner" /> Finding products...
                  </>
                ) : (
                  "Find Products ->"
                )}
              </button>
            </div>
            {phase !== "idle" && getProgressLabel() && (
              <div className="progress-row">
                <span className={`progress-pill ${isStreaming ? "progress-pill--active" : ""}`}>
                  {getProgressLabel()}
                </span>
              </div>
            )}
            {backendError && <p className="backend-error">{backendError}</p>}
          </div>

          {visibleRecommendations.length > 0 && (
            <div className="recommendations-section">
              <div className="recs-header">
                <div className="recs-header-copy">
                  <h3 className="recs-title">Recommended For You</h3>
                  <p className="recs-subtitle">
                    {recommendMode === "fast"
                      ? "Matched instantly from your local vector index"
                      : "Selected locally by llama3.2:3b from vector-search candidates"}
                  </p>
                </div>
                {phase === "done" && <span className="done-badge">Complete</span>}
              </div>
              <div className="recs-grid">
                {visibleRecommendations.map((rec, index) => (
                  (() => {
                    const resolvedProduct = resolveRecommendationProduct(rec);

                    return (
                      <div
                        key={resolvedProduct?.id || `${normalizeTitle(rec.title)}-${index}`}
                        className="rec-card"
                      >
                    <div className="rec-thumb">
                      {resolvedProduct?.thumbnail ? (
                        <img src={resolvedProduct.thumbnail} alt={rec.title} />
                      ) : (
                        <div className="rec-thumb-placeholder">
                          {rec.title.charAt(0)}
                        </div>
                      )}
                    </div>
                    <div className="rec-info">
                      <p className="rec-title">{rec.title}</p>
                      <p className="rec-desc">{rec.description?.slice(0, 80)}...</p>
                      {resolvedProduct &&
                        resolvedProduct.variants &&
                        resolvedProduct.variants.length > 1 && (
                          <label className="variant-picker">
                            <span className="variant-picker-label">Variant</span>
                            <select
                              className="variant-select"
                              value={
                                selectedVariants[resolvedProduct.id] ||
                                getDefaultVariant(resolvedProduct)?.id ||
                                ""
                              }
                              onChange={(event) => {
                                setSelectedVariants((prev) => ({
                                  ...prev,
                                  [resolvedProduct.id]: event.target.value,
                                }));
                              }}
                            >
                              {resolvedProduct.variants.map((variant) => (
                                <option key={variant.id} value={variant.id}>
                                  {getVariantLabel(variant)} -{" "}
                                  {getPriceLabel(resolvedProduct, variant.id)}
                                </option>
                              ))}
                            </select>
                          </label>
                        )}
                      {getOptionSummary(resolvedProduct) && (
                        <p className="rec-meta">{getOptionSummary(resolvedProduct)}</p>
                      )}
                      <div className="rec-footer">
                        <span className="rec-price">
                          {getPriceLabel(
                            resolvedProduct,
                            resolvedProduct
                              ? selectedVariants[resolvedProduct.id]
                              : undefined
                          )}
                        </span>
                        <button
                          className={`add-btn ${
                            resolvedProduct && addedItems.has(resolvedProduct.id)
                              ? "add-btn--added"
                              : ""
                          }`}
                          onClick={() => resolvedProduct && addToCart(resolvedProduct)}
                          disabled={!resolvedProduct}
                        >
                          {resolvedProduct && addedItems.has(resolvedProduct.id)
                            ? "Added!"
                            : "+ Add to Cart"}
                        </button>
                      </div>
                    </div>
                      </div>
                    );
                  })()
                ))}
              </div>
            </div>
          )}

          {(visibleRecommendations.length > 0 || traceSteps.length > 0) && (
            <div className="trace-section">
              <div className="trace-header">
                <div>
                  <h3 className="trace-title">How the AI Decided</h3>
                  <p className="trace-subtitle">
                    Short local decision trace for stakeholders
                  </p>
                </div>
                <span className="trace-badge">Local Trace</span>
              </div>
              <div className="trace-grid">
                {traceSteps.length > 0 ? (
                  traceSteps.map((step, index) => (
                    <div key={`${step}-${index}`} className="trace-card">
                      <span className="trace-step">{index + 1}</span>
                      <p className="trace-copy">{step}</p>
                    </div>
                  ))
                ) : (
                  <p className="trace-placeholder">
                    The local model is preparing a short decision trace...
                  </p>
                )}
              </div>
            </div>
          )}

          {(visibleRecommendations.length > 0 || insightText) && (
            <div className="insight-section">
              <div className="insight-header">
                <div>
                  <h3 className="insight-title">Why These Picks</h3>
                  <p className="insight-subtitle">
                    Generated locally by llama3.2:3b on this machine
                  </p>
                </div>
                <span className="insight-badge">Edge AI</span>
              </div>
              <div className="insight-body">
                {insightText ? (
                  <p className="insight-text">{insightText}</p>
                ) : (
                  <p className="insight-placeholder">
                    DeepSeek is preparing a local explanation for these matches...
                  </p>
                )}
              </div>
            </div>
          )}

          {phase === "idle" && (
            <div className="idle-state">
              <div className="idle-suggestions">
                <p className="suggestions-label">Try asking:</p>
                {[
                  "I want to start running outdoors",
                  "I need gear for a home workout",
                  "Looking for a gift for a fitness lover",
                  "I want to recover faster after exercise",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    className="suggestion-chip"
                    onClick={() => setQuery(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
              <div className="idle-features">
                <div className="feature">Streams token by token</div>
                <div className="feature">Zero data leaves device</div>
                <div className="feature">Full reasoning transparency</div>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
