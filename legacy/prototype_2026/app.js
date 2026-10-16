const state = {
  lang: "ar",
  markets: [
    { symbol: "GC", asset: "Gold", nameAr: "الذهب", nameEn: "Gold Futures", price: "API Ready", change: "Awaiting feed", trend: "flat", noteAr: "جاهز للربط بسعر CME أو مزود أسعار موثوق.", noteEn: "Ready for CME or trusted price feed integration." },
    { symbol: "SI", asset: "Silver", nameAr: "الفضة", nameEn: "Silver Futures", price: "API Ready", change: "Awaiting feed", trend: "flat", noteAr: "يدعم SI / SIC / SI1000 بعد ربط البيانات.", noteEn: "Supports SI / SIC / SI1000 after data integration." },
    { symbol: "CL", asset: "Oil", nameAr: "النفط", nameEn: "Crude Oil", price: "API Ready", change: "Awaiting feed", trend: "flat", noteAr: "جاهز لربط WTI / Brent أو بيانات EIA لاحقًا.", noteEn: "Ready for WTI / Brent or EIA data integration later." },
    { symbol: "TQQQ", asset: "Equities", nameAr: "الأسهم", nameEn: "Equities", price: "API Ready", change: "Awaiting feed", trend: "flat", noteAr: "قابل لإضافة META / NVDA / MSFT / APP وغيرها.", noteEn: "Ready for META / NVDA / MSFT / APP and more." }
  ],
  news: [
    { asset: "gold", source: "News API placeholder", time: "Dubai UTC+4", titleAr: "خبر الذهب سيظهر هنا بعد ربط مصدر الأخبار", titleEn: "Gold news will appear here after API integration", textAr: "هذه بطاقة تجريبية. الهدف النهائي هو فلترة أخبار الذهب فقط داخل النسخة العربية والإنجليزية حسب اللغة المختارة.", textEn: "Prototype card. The final app will filter gold-specific headlines by selected language." },
    { asset: "silver", source: "News API placeholder", time: "Dubai UTC+4", titleAr: "خبر الفضة سيظهر هنا بعد ربط مصدر الأخبار", titleEn: "Silver news will appear here after API integration", textAr: "يمكن ربط الفضة بمصادر أخبار وأسعار منفصلة عن الذهب لتجنب الخلط بين الأدوات.", textEn: "Silver can be linked to dedicated news and price feeds to avoid cross-asset noise." },
    { asset: "oil", source: "News API placeholder", time: "Dubai UTC+4", titleAr: "خبر النفط سيظهر هنا بعد ربط مصدر الأخبار", titleEn: "Oil news will appear here after API integration", textAr: "القسم مهيأ لتغطية المخزون الأمريكي، أوبك، المخاطر الجيوسياسية، وحركة العقود.", textEn: "Prepared for US inventories, OPEC, geopolitical risk, and futures flow." },
    { asset: "equities", source: "News API placeholder", time: "Dubai UTC+4", titleAr: "أخبار الأسهم ستظهر هنا بعد الربط", titleEn: "Equity news will appear here after integration", textAr: "القسم قابل للتخصيص للأسهم التقنية والرافعة المالية مثل TQQQ و NVDA و META.", textEn: "Customizable for technology and leveraged names such as TQQQ, NVDA and META." }
  ],
  scenarios: [
    { labelAr: "سيناريو صاعد", labelEn: "Bullish Scenario", probability: 45, textAr: "يتفعل عند توافق الأخبار، السعر، والزخم الفني في اتجاه واحد.", textEn: "Activated when news flow, price action, and technical momentum align." },
    { labelAr: "سيناريو محايد", labelEn: "Neutral Scenario", probability: 35, textAr: "نطاق تذبذب حتى ظهور محفز واضح من البيانات أو الأخبار.", textEn: "Range-bound flow until a clear data or news catalyst appears." },
    { labelAr: "سيناريو هابط", labelEn: "Bearish Scenario", probability: 20, textAr: "يتفعل عند كسر مستويات الدعم أو تحسن شهية المخاطرة ضد المعادن.", textEn: "Activated on support breaks or stronger risk appetite against metals." }
  ],
  i18n: {
    ar: {
      heroTitle: "نبض الأسواق في لوحة واحدة",
      heroText: "متابعة منظمة للذهب والفضة والنفط والأسهم، مع أخبار مختارة وسيناريوهات قابلة للتحديث عبر API.",
      marketsTitle: "لوحة الأسواق",
      newsTitle: "الأخبار المختارة",
      scenarioTitle: "سيناريوهات العمل",
      updated: "آخر تحديث تجريبي",
      vision: ["واجهة عربية أولًا مع دعم إنجليزي كامل.", "مصممة للربط لاحقًا مع أسعار وأخبار حقيقية.", "قابلة للتطوير إلى تقارير SoloSophy التفاعلية."],
    },
    en: {
      heroTitle: "Market pulse in one command board",
      heroText: "Structured coverage for gold, silver, oil and equities, with selected news and API-ready scenarios.",
      marketsTitle: "Market Board",
      newsTitle: "Selected News",
      scenarioTitle: "Operating Scenarios",
      updated: "Prototype updated",
      vision: ["Arabic-first interface with full English support.", "Built for future live prices and news feeds.", "Expandable into interactive SoloSophy reports."],
    }
  }
};

const marketGrid = document.getElementById("marketGrid");
const newsList = document.getElementById("newsList");
const scenarioList = document.getElementById("scenarioList");
const visionList = document.getElementById("visionList");
const assetFilter = document.getElementById("assetFilter");
const lastUpdated = document.getElementById("lastUpdated");
const sessionState = document.getElementById("sessionState");

function t(key) {
  return state.i18n[state.lang][key];
}

function renderText() {
  document.documentElement.lang = state.lang;
  document.documentElement.dir = state.lang === "ar" ? "rtl" : "ltr";

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });

  visionList.innerHTML = state.i18n[state.lang].vision.map((item) => `<li>${item}</li>`).join("");

  const now = new Date();
  lastUpdated.textContent = `${t("updated")}: ${now.toLocaleString(state.lang === "ar" ? "ar-AE" : "en-AE", { timeZone: "Asia/Dubai" })}`;
  sessionState.textContent = `Dubai UTC+4 · ${now.toLocaleTimeString(state.lang === "ar" ? "ar-AE" : "en-AE", { timeZone: "Asia/Dubai", hour: "2-digit", minute: "2-digit" })}`;
}

function renderMarkets() {
  marketGrid.innerHTML = state.markets.map((item) => {
    const title = state.lang === "ar" ? item.nameAr : item.nameEn;
    const note = state.lang === "ar" ? item.noteAr : item.noteEn;
    return `
      <article class="market-card" data-symbol="${item.symbol}">
        <div class="market-title"><span>${title}</span><span>${item.symbol}</span></div>
        <div class="price">${item.price}</div>
        <div class="change ${item.trend}">${item.change}</div>
        <p>${note}</p>
      </article>
    `;
  }).join("");
}

function renderNews() {
  const selected = assetFilter.value;
  const items = state.news.filter((item) => selected === "all" || item.asset === selected);
  newsList.innerHTML = items.map((item) => `
    <article class="news-card">
      <div class="news-meta"><span>${item.source}</span><span>•</span><span>${item.time}</span></div>
      <h3>${state.lang === "ar" ? item.titleAr : item.titleEn}</h3>
      <p>${state.lang === "ar" ? item.textAr : item.textEn}</p>
    </article>
  `).join("");
}

function renderScenarios() {
  scenarioList.innerHTML = state.scenarios.map((item) => `
    <article class="scenario-card">
      <div class="probability"><span>${state.lang === "ar" ? item.labelAr : item.labelEn}</span><span>${item.probability}%</span></div>
      <div class="bar"><span style="width: ${item.probability}%"></span></div>
      <p>${state.lang === "ar" ? item.textAr : item.textEn}</p>
    </article>
  `).join("");
}

function render() {
  renderText();
  renderMarkets();
  renderNews();
  renderScenarios();
}

document.querySelectorAll("[data-lang]").forEach((button) => {
  button.addEventListener("click", () => {
    state.lang = button.dataset.lang;
    document.querySelectorAll("[data-lang]").forEach((node) => node.classList.remove("active"));
    button.classList.add("active");
    render();
  });
});

assetFilter.addEventListener("change", renderNews);
document.getElementById("refreshBtn").addEventListener("click", render);

render();
