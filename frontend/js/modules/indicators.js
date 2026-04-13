/* ── Indicator Engine v2 ─────────────────────────────────────────── */

// ── Math helpers ──────────────────────────────────────────────────
function _ema(arr, p) {
  const k = 2/(p+1); let prev = null; const out = [];
  for (let i=0;i<arr.length;i++) {
    if (i < p-1) { out.push(null); continue; }
    if (prev===null) { prev = arr.slice(0,p).reduce((a,b)=>a+b,0)/p; out.push(prev); }
    else { prev = arr[i]*k + prev*(1-k); out.push(prev); }
  } return out;
}
function _sma(arr, p) {
  return arr.map((_,i) => i<p-1 ? null : arr.slice(i-p+1,i+1).reduce((a,b)=>a+b,0)/p);
}

// ── Compute all indicator values from candles ─────────────────────
export function computeAllIndicators(candles) {
  if (!candles || candles.length < 15) return {};
  const C=candles.map(c=>c.c), H=candles.map(c=>c.h), L=candles.map(c=>c.l);
  const V=candles.map(c=>c.v||1e4), n=candles.length, Z=n-1;
  const res = {};

  // MA20
  const ma20s = _sma(C,20); const m20=ma20s[Z];
  res.MA20={val:m20, display:m20?(C[Z]>m20?'Above':'Below'):'—', signal:m20?(C[Z]>m20?'bullish':'bearish'):'neutral', series:ma20s};

  // MA60
  const ma60s = _sma(C,Math.min(60,n)); const m60=ma60s[Z];
  res.MA60={val:m60, display:m60?(C[Z]>m60?'Above':'Below'):'—', signal:m60?(C[Z]>m60?'bullish':'bearish'):'neutral', series:ma60s};

  // MACD
  const e12=_ema(C,12), e26=_ema(C,26);
  const ml=e12.map((v,i)=>v!=null&&e26[i]!=null?v-e26[i]:null);
  const validMl=ml.filter(v=>v!==null);
  const sig9=_ema(validMl,9);
  const sigFull=new Array(ml.length-sig9.length).fill(null).concat(sig9);
  const ml_z=ml[Z], sig_z=sigFull[Z];
  const hist_z=ml_z!=null&&sig_z!=null?ml_z-sig_z:null;
  res.MACD={val:hist_z, display:hist_z!=null?(hist_z>=0?'+'+hist_z.toFixed(3):hist_z.toFixed(3)):'—',
    signal:hist_z!=null?(hist_z>0?'bullish':'bearish'):'neutral', macdLine:ml, signalLine:sigFull,
    hist:ml.map((v,i)=>v!=null&&sigFull[i]!=null?v-sigFull[i]:null)};

  // RSI(14)
  const chg=C.map((c,i)=>i===0?0:c-C[i-1]);
  let aG=0,aL=0;
  for(let i=1;i<=14;i++){aG+=Math.max(0,chg[i]);aL+=Math.max(0,-chg[i]);}
  aG/=14;aL/=14;
  for(let i=15;i<n;i++){aG=(aG*13+Math.max(0,chg[i]))/14;aL=(aL*13+Math.max(0,-chg[i]))/14;}
  const rsi=aL===0?100:100-100/(1+aG/aL);
  // full RSI series for chart
  const rsiS=[];
  {let g=0,l=0;
   for(let i=1;i<=14&&i<n;i++){g+=Math.max(0,chg[i]);l+=Math.max(0,-chg[i]);}
   g/=14;l/=14; for(let i=0;i<14;i++)rsiS.push(null);
   rsiS.push(l===0?100:100-100/(1+g/l));
   for(let i=15;i<n;i++){g=(g*13+Math.max(0,chg[i]))/14;l=(l*13+Math.max(0,-chg[i]))/14;rsiS.push(l===0?100:100-100/(1+g/l));}}
  res.RSI={val:rsi, display:rsi.toFixed(1), signal:rsi>70?'overbought':rsi<30?'oversold':rsi>50?'bullish':'neutral', series:rsiS};

  // KDJ(9)
  let k=50,d=50;
  for(let i=Math.min(8,n-1);i<n;i++){
    const sh=Math.max(...H.slice(Math.max(0,i-8),i+1));
    const sl=Math.min(...L.slice(Math.max(0,i-8),i+1));
    const rsv=sh===sl?50:(C[i]-sl)/(sh-sl)*100;
    k=2/3*k+1/3*rsv; d=2/3*d+1/3*k;
  }
  const j=3*k-2*d;
  res.KDJ={val:{k,d,j}, display:`K:${k.toFixed(0)} D:${d.toFixed(0)}`, signal:k>80?'overbought':k<20?'oversold':k>d?'bullish':'bearish'};

  // CCI(20)
  const TP=candles.map(c=>(c.h+c.l+c.c)/3);
  const tpSma=_sma(TP,20); const tpM=tpSma[Z]||TP[Z];
  let md=0; for(let i=Math.max(0,Z-19);i<=Z;i++)md+=Math.abs(TP[i]-tpM); md/=20;
  const cci=md===0?0:(TP[Z]-tpM)/(0.015*md);
  const cciS=TP.map((_,i)=>{
    if(i<19)return null;
    const m=tpSma[i]||TP[i]; let d2=0;
    for(let j=i-19;j<=i;j++)d2+=Math.abs(TP[j]-m); d2/=20;
    return d2===0?0:(TP[i]-m)/(0.015*d2);
  });
  res.CCI={val:cci, display:cci.toFixed(0), signal:cci>100?'overbought':cci<-100?'oversold':cci>0?'bullish':'bearish', series:cciS};

  // Williams %R(14)
  const wH=Math.max(...H.slice(Math.max(0,Z-13),Z+1));
  const wL=Math.min(...L.slice(Math.max(0,Z-13),Z+1));
  const willr=wH===wL?-50:(wH-C[Z])/(wH-wL)*-100;
  res.WILLR={val:willr, display:willr.toFixed(1)+'%', signal:willr>-20?'overbought':willr<-80?'oversold':willr>-50?'bullish':'bearish'};

  // ROC(10)
  const roc=Z>=10?(C[Z]-C[Z-10])/C[Z-10]*100:0;
  const rocS=C.map((_,i)=>i<10?null:(C[i]-C[i-10])/C[i-10]*100);
  res.ROC={val:roc, display:(roc>=0?'+':'')+roc.toFixed(2)+'%', signal:roc>3?'bullish':roc<-3?'bearish':'neutral', series:rocS};

  // ADX(14) — simplified via DI
  let sTR=0,sPDM=0,sNDM=0;
  for(let i=1;i<n;i++){
    sTR+=Math.max(H[i]-L[i],Math.abs(H[i]-C[i-1]),Math.abs(L[i]-C[i-1]));
    sPDM+=Math.max(0,H[i]-H[i-1]); sNDM+=Math.max(0,L[i-1]-L[i]);
  }
  const pdi=sTR>0?sPDM/sTR*100:0, ndi=sTR>0?sNDM/sTR*100:0;
  const dx=(pdi+ndi)>0?Math.abs(pdi-ndi)/(pdi+ndi)*100:0;
  const adx=Math.min(100,dx);
  res.ADX={val:adx, display:adx.toFixed(0), signal:adx>25?(pdi>ndi?'bullish':'bearish'):'neutral', pdi:pdi.toFixed(1), ndi:ndi.toFixed(1)};

  // Ichimoku
  const tenP=Math.min(9,n), kijP=Math.min(26,n);
  const ten=(Math.max(...H.slice(Z-tenP+1,Z+1))+Math.min(...L.slice(Z-tenP+1,Z+1)))/2;
  const kij=(Math.max(...H.slice(Math.max(0,Z-kijP+1),Z+1))+Math.min(...L.slice(Math.max(0,Z-kijP+1),Z+1)))/2;
  const sA=(ten+kij)/2;
  const sB=(Math.max(...H.slice(Math.max(0,Z-51),Z+1))+Math.min(...L.slice(Math.max(0,Z-51),Z+1)))/2;
  const cTop=Math.max(sA,sB), cBot=Math.min(sA,sB);
  res.ICHIMOKU={val:{ten,kij,sA,sB,cTop,cBot},
    display:C[Z]>cTop?'Cloud Above':C[Z]<cBot?'Cloud Below':'In Cloud',
    signal:C[Z]>cTop?'bullish':C[Z]<cBot?'bearish':'neutral'};

  // Parabolic SAR
  let bull=true,ep=H[0],af=0.02,psar=L[0];
  for(let i=1;i<n;i++){
    psar=psar+af*(ep-psar);
    if(bull){
      if(L[i]<psar){bull=false;psar=ep;ep=L[i];af=0.02;}
      else if(H[i]>ep){ep=H[i];af=Math.min(0.2,af+0.02);}
    } else {
      if(H[i]>psar){bull=true;psar=ep;ep=H[i];af=0.02;}
      else if(L[i]<ep){ep=L[i];af=Math.min(0.2,af+0.02);}
    }
  }
  res.PSAR={val:psar, display:bull?'Buy ▲':'Sell ▼', signal:bull?'bullish':'bearish'};

  // Bollinger(20)
  const bMid=_sma(C,20)[Z]||C[Z];
  let bStd=0; for(let i=Math.max(0,Z-19);i<=Z;i++)bStd+=(C[i]-bMid)**2; bStd=Math.sqrt(bStd/20);
  const bUp=bMid+2*bStd, bLo=bMid-2*bStd;
  const bPct=(bUp>bLo)?(C[Z]-bLo)/(bUp-bLo):0.5;
  res.BOLL={val:bPct, display:bPct>0.8?'Upper Band':bPct<0.2?'Lower Band':'Mid Band',
    signal:bPct>0.8?'overbought':bPct<0.2?'oversold':'neutral', upper:bUp, mid:bMid, lower:bLo};

  // ATR(14)
  const trArr=[];
  for(let i=1;i<n;i++)trArr.push(Math.max(H[i]-L[i],Math.abs(H[i]-C[i-1]),Math.abs(L[i]-C[i-1])));
  const atr=trArr.slice(-14).reduce((a,b)=>a+b,0)/Math.min(14,trArr.length);
  const atrPct=atr/C[Z]*100;
  res.ATR={val:atr, display:atr.toFixed(2), signal:atrPct>2?'volatile':atrPct>1?'neutral':'stable'};

  // Keltner Channel
  const kEma=_ema(C,20); const kMid=kEma[Z]||C[Z];
  const kUp=kMid+2*atr, kLo=kMid-2*atr;
  const kPct=(kUp>kLo)?(C[Z]-kLo)/(kUp-kLo):0.5;
  res.KELTNER={val:kPct, display:kPct>0.8?'Upper':kPct<0.2?'Lower':'Mid',
    signal:kPct>0.8?'overbought':kPct<0.2?'oversold':'neutral', upper:kUp, mid:kMid, lower:kLo};

  // Volume ratio
  const vAvg=V.slice(-20).reduce((a,b)=>a+b,0)/Math.min(20,V.length);
  const vRatio=V[Z]/vAvg;
  res.VOLUME={val:vRatio, display:vRatio.toFixed(1)+'x', signal:vRatio>1.5?'bullish':vRatio<0.5?'bearish':'neutral'};

  // OBV
  let obv=0; const obvS=[0];
  for(let i=1;i<n;i++){obv+=C[i]>C[i-1]?V[i]:C[i]<C[i-1]?-V[i]:0; obvS.push(obv);}
  const obvSma=_sma(obvS,10);
  res.OBV={val:obv, display:(obv>=0?'+':'')+Math.round(obv/1000)+'K',
    signal:obv>(obvSma[Z]||0)?'bullish':'bearish', series:obvS};

  // CMF(20)
  let mfv=0,mvol=0;
  for(let i=Math.max(0,Z-19);i<=Z;i++){
    const r=H[i]-L[i];
    if(r>0){const m=((C[i]-L[i])-(H[i]-C[i]))/r; mfv+=m*V[i];}
    mvol+=V[i];
  }
  const cmf=mvol>0?mfv/mvol:0;
  res.CMF={val:cmf, display:(cmf>=0?'+':'')+cmf.toFixed(3), signal:cmf>0.1?'bullish':cmf<-0.1?'bearish':'neutral'};

  // Fibonacci
  const fH=Math.max(...H), fL=Math.min(...L), fR=fH-fL;
  const fPct=fR>0?(C[Z]-fL)/fR:0.5;
  res.FIB={val:fPct, display:(fPct*100).toFixed(0)+'%',
    signal:fPct>0.618?'bullish':fPct<0.382?'bearish':'neutral',
    levels:{h:fH,l:fL,r618:fL+fR*0.618,r500:fL+fR*0.5,r382:fL+fR*0.382,r236:fL+fR*0.236}};

  // S/R
  const rH=Math.max(...H.slice(-20)), rL=Math.min(...L.slice(-20));
  const srPct=(rH>rL)?(C[Z]-rL)/(rH-rL):0.5;
  res.SR={val:{sup:rL,res:rH}, display:srPct>0.8?'Near Resist.':srPct<0.2?'Near Support':'Mid Range',
    signal:srPct>0.8?'overbought':srPct<0.2?'oversold':'neutral'};

  return res;
}

// ── Group / meta definitions ──────────────────────────────────────
export const IND_GROUPS = [
  { key:'trend',    zh:'趋势增强', en:'Trend',       items:['MA20','MA60','MACD','ADX','ICHIMOKU','PSAR'] },
  { key:'momentum', zh:'动量振荡', en:'Momentum',    items:['RSI','KDJ','CCI','WILLR','ROC'] },
  { key:'volatile', zh:'波动率',   en:'Volatility',  items:['BOLL','ATR','KELTNER'] },
  { key:'volume',   zh:'成交量',   en:'Volume',      items:['VOLUME','OBV','CMF'] },
  { key:'sr',       zh:'支撑阻力', en:'Support/Res', items:['FIB','SR'] },
];

export const SIG_CFG = {
  bullish:    {cls:'sig-bull', zh:'多头', en:'Bull'},
  bearish:    {cls:'sig-bear', zh:'空头', en:'Bear'},
  overbought: {cls:'sig-ob',   zh:'超买', en:'OB'},
  oversold:   {cls:'sig-os',   zh:'超卖', en:'OS'},
  neutral:    {cls:'sig-neu',  zh:'中性', en:'Neu'},
  volatile:   {cls:'sig-vol',  zh:'高波', en:'High'},
  stable:     {cls:'sig-sta',  zh:'稳定', en:'Low'},
};

export const IND_META = {
  MA20:     {zh:'MA20 均线',    en:'MA20',            icon:'📈', chartType:'price_overlay'},
  MA60:     {zh:'MA60 均线',    en:'MA60',            icon:'📊', chartType:'price_overlay'},
  MACD:     {zh:'MACD',        en:'MACD',            icon:'⚡', chartType:'macd'},
  ADX:      {zh:'ADX 趋向指数',  en:'ADX',             icon:'🎯', chartType:'oscillator'},
  ICHIMOKU: {zh:'一目均衡表',   en:'Ichimoku Cloud',  icon:'☁️', chartType:'ichimoku'},
  PSAR:     {zh:'抛物线转向',   en:'Parabolic SAR',   icon:'🔄', chartType:'price_overlay'},
  RSI:      {zh:'RSI 相对强弱', en:'RSI (14)',         icon:'📉', chartType:'oscillator'},
  KDJ:      {zh:'KDJ 随机指标', en:'KDJ',             icon:'🌀', chartType:'oscillator'},
  CCI:      {zh:'CCI 顺势指标', en:'CCI',             icon:'🌊', chartType:'oscillator'},
  WILLR:    {zh:'威廉指标 %R',  en:'Williams %R',     icon:'🎭', chartType:'oscillator'},
  ROC:      {zh:'ROC 变动率',   en:'ROC',             icon:'🚀', chartType:'oscillator'},
  BOLL:     {zh:'布林带',       en:'Bollinger Bands', icon:'🎪', chartType:'band'},
  ATR:      {zh:'ATR 真实波幅', en:'ATR',             icon:'💨', chartType:'oscillator'},
  KELTNER:  {zh:'肯特纳通道',   en:'Keltner Channel', icon:'🏔️', chartType:'band'},
  VOLUME:   {zh:'成交量比',     en:'Volume Ratio',    icon:'📦', chartType:'volume'},
  OBV:      {zh:'OBV 能量潮',   en:'OBV',             icon:'🌊', chartType:'line'},
  CMF:      {zh:'CMF 货币流量', en:'CMF',             icon:'💰', chartType:'oscillator'},
  FIB:      {zh:'斐波那契回撤', en:'Fibonacci',       icon:'🔢', chartType:'price_overlay'},
  SR:       {zh:'支撑阻力位',   en:'Support/Resist.', icon:'🏗️', chartType:'price_overlay'},
};

// ── Full detail info for modal ────────────────────────────────────
export const IND_DETAIL = {
  MA20: {
    fullName:{zh:'MA20 — 20日移动平均线',en:'MA20 — 20-Day Moving Average'},
    desc:{zh:'将过去20个交易日的收盘价取平均，平滑价格波动，判断中短期趋势。',en:'Averages the last 20 closing prices to smooth price action and identify medium-term trends.'},
    formula:{zh:'MA20 = (C₁ + C₂ + … + C₂₀) / 20',en:'MA20 = (C₁ + C₂ + … + C₂₀) / 20'},
    calc:{zh:'每日将最近20个收盘价求和再除以20，随着新K线形成，最旧的价格自动移出，保持窗口为20日。',en:'Sum the most recent 20 closing prices and divide by 20. As each new bar forms, the oldest price drops out.'},
    signals:{zh:[['价格在MA上方','多头排列','上升趋势','pos'],['价格穿越MA向上','金叉买入信号','趋势转多','pos'],['价格在MA下方','空头排列','下降趋势','neg'],['价格穿越MA向下','死叉卖出信号','趋势转空','neg']],
              en:[['Price above MA','Bullish alignment','Uptrend','pos'],['Price crosses above','Golden cross','Trend turns up','pos'],['Price below MA','Bearish alignment','Downtrend','neg'],['Price crosses below','Death cross','Trend turns down','neg']]}
  },
  MA60: {
    fullName:{zh:'MA60 — 60日移动平均线',en:'MA60 — 60-Day Moving Average'},
    desc:{zh:'60日均线是重要的中长期趋势参考线，代表约三个月的市场均价，常被视为"生命线"。',en:'The 60-day MA is a critical medium-long term reference, representing ~3 months of market average, often called the "lifeline".'},
    formula:{zh:'MA60 = Σ(Cᵢ) / 60，i从1到60',en:'MA60 = Σ(Cᵢ) / 60, i from 1 to 60'},
    calc:{zh:'取最近60个交易日的收盘价求算术平均，时间窗口更长，对短期价格噪音的过滤能力更强。',en:'Calculate arithmetic mean of the last 60 trading-day closes. The longer window filters out short-term noise more effectively.'},
    signals:{zh:[['价格持续站稳MA60上方','长线多头趋势确认','持股或加仓','pos'],['价格跌破MA60','中长期趋势转弱','减仓观察','neg'],['MA60向上倾斜','市场整体趋势向好','','pos'],['MA60向下倾斜','市场整体趋势向空','','neg']],
              en:[['Price sustains above MA60','Long-term bull confirmed','Hold/add','pos'],['Price breaks below MA60','Medium-term trend weakens','Reduce/watch','neg'],['MA60 slopes up','Overall trend positive','','pos'],['MA60 slopes down','Overall trend negative','','neg']]}
  },
  MACD: {
    fullName:{zh:'MACD — 指数平滑异同移动平均线',en:'MACD — Moving Average Convergence Divergence'},
    desc:{zh:'通过计算12日与26日EMA的差值来识别趋势的动量和转折点，是最常用的趋势动量指标。',en:'Identifies trend momentum and turning points via the difference between 12-day and 26-day EMAs. One of the most widely-used technical indicators.'},
    formula:{zh:'MACD线 = EMA(12) − EMA(26)\n信号线 = EMA(MACD线, 9)\n柱状图 = MACD线 − 信号线',en:'MACD Line = EMA(12) − EMA(26)\nSignal = EMA(MACD Line, 9)\nHistogram = MACD Line − Signal'},
    calc:{zh:'1. 计算12日指数移动平均EMA12\n2. 计算26日指数移动平均EMA26\n3. MACD线 = EMA12 - EMA26\n4. 对MACD线再做9日EMA得到信号线\n5. 柱状图 = MACD线 - 信号线',en:'1. Compute 12-day EMA\n2. Compute 26-day EMA\n3. MACD Line = EMA12 - EMA26\n4. Apply 9-day EMA to MACD Line for Signal\n5. Histogram = MACD Line - Signal'},
    signals:{zh:[['柱状图由负转正','金叉，买入信号','动能由空转多','pos'],['柱状图由正转负','死叉，卖出信号','动能由多转空','neg'],['MACD线上穿0轴','上升趋势确认','','pos'],['背离：价格新高但MACD不新高','顶背离，见顶信号','','neg']],
              en:[['Histogram neg→pos','Golden cross, buy signal','Momentum turns bullish','pos'],['Histogram pos→neg','Death cross, sell signal','Momentum turns bearish','neg'],['MACD crosses above zero','Uptrend confirmation','','pos'],['Divergence: price new high but MACD lower','Bearish divergence, top signal','','neg']]}
  },
  ADX: {
    fullName:{zh:'ADX — 平均趋向指数',en:'ADX — Average Directional Index'},
    desc:{zh:'ADX衡量趋势的强度，而不判断方向。+DI代表上涨力量，-DI代表下跌力量。',en:'ADX measures trend strength without indicating direction. +DI represents upward force, -DI represents downward force.'},
    formula:{zh:'TR = max(H-L, |H-C₋₁|, |L-C₋₁|)\n+DI = 100 × EMA(+DM) / EMA(TR)\n-DI = 100 × EMA(-DM) / EMA(TR)\nDX = 100 × |+DI − -DI| / (+DI + -DI)\nADX = EMA(DX, 14)',en:'TR = max(H-L, |H-Prev Close|, |L-Prev Close|)\n+DI = 100 × EMA(+DM) / EMA(TR)\n-DI = 100 × EMA(-DM) / EMA(TR)\nDX = 100 × |+DI − -DI| / (+DI + -DI)\nADX = EMA(DX, 14)'},
    calc:{zh:'1. 计算真实波幅TR\n2. 计算方向运动+DM和-DM\n3. 平滑后得到+DI和-DI\n4. DX反映两个DI的差距比例\n5. ADX对DX做14日平滑',en:'1. Calculate True Range (TR)\n2. Calculate directional movements +DM and -DM\n3. Smooth to get +DI and -DI\n4. DX reflects the spread between the DIs\n5. ADX smooths DX over 14 periods'},
    signals:{zh:[['ADX > 25','强趋势行情','趋势跟踪策略有效','pos'],['ADX < 20','震荡行情','趋势策略慎用，适合均值回归',''],['ADX上升 + +DI > -DI','上涨趋势增强','做多','pos'],['ADX上升 + -DI > +DI','下跌趋势增强','做空','neg']],
              en:[['ADX > 25','Strong trend','Trend-following strategies work','pos'],['ADX < 20','Choppy market','Avoid trend strategies, use mean-reversion',''],['ADX rising + +DI > -DI','Uptrend strengthening','Go long','pos'],['ADX rising + -DI > +DI','Downtrend strengthening','Go short','neg']]}
  },
  ICHIMOKU: {
    fullName:{zh:'一目均衡表 — Ichimoku Cloud',en:'Ichimoku Cloud — All-in-One Indicator'},
    desc:{zh:'由五条线组成的全能型指标，通过"云带"同时展示趋势、支撑和阻力，是日本最流行的技术分析工具之一。',en:'A comprehensive 5-line indicator that simultaneously shows trend, support, and resistance via the "cloud". One of Japan\'s most popular technical tools.'},
    formula:{zh:'转换线 = (9日最高 + 9日最低) / 2\n基准线 = (26日最高 + 26日最低) / 2\n先行A = (转换线 + 基准线) / 2\n先行B = (52日最高 + 52日最低) / 2\n迟行带 = 当前收盘，向前移动26日',en:'Tenkan = (9H + 9L) / 2\nKijun = (26H + 26L) / 2\nSenkou A = (Tenkan + Kijun) / 2\nSenkou B = (52H + 52L) / 2\nChikou = Current close, shifted back 26 bars'},
    calc:{zh:'各线代表不同时间周期的中点价格，形成的云带（先行A和B之间的区域）代表当前的支撑或阻力区。',en:'Each line represents the midpoint of different time horizons. The cloud between Senkou A and B represents current support/resistance.'},
    signals:{zh:[['价格在云上方','强多头趋势','云越厚支撑越强','pos'],['价格在云下方','强空头趋势','云越厚阻力越强','neg'],['价格在云内','趋势不明朗','等待突破方向',''],['转换线上穿基准线','短期金叉买入','','pos']],
              en:[['Price above cloud','Strong bullish trend','Thicker cloud = stronger support','pos'],['Price below cloud','Strong bearish trend','Thicker cloud = stronger resistance','neg'],['Price inside cloud','Uncertain trend','Wait for breakout direction',''],['Tenkan crosses above Kijun','Short-term golden cross','','pos']]}
  },
  PSAR: {
    fullName:{zh:'抛物线转向指标 — Parabolic SAR',en:'Parabolic SAR — Stop and Reverse'},
    desc:{zh:'在图表上方或下方显示为点状，主要用于追踪止损和判断趋势反转点。',en:'Plotted as dots above or below price bars. Primarily used for trailing stops and identifying trend reversal points.'},
    formula:{zh:'SAR₍ₙ₎ = SAR₍ₙ₋₁₎ + AF × (EP − SAR₍ₙ₋₁₎)\nAF: 加速因子，初始0.02，每次创新高/低增加0.02，最大0.2\nEP: 极值点（趋势中的最高/最低价）',en:'SAR(n) = SAR(n-1) + AF × (EP − SAR(n-1))\nAF: Acceleration Factor, starts at 0.02, increases by 0.02 on new EP, max 0.2\nEP: Extreme Point (highest/lowest price in trend)'},
    calc:{zh:'1. 上升趋势中SAR在价格下方追踪\n2. 当价格跌破SAR，转为下降趋势，SAR移至价格上方\n3. AF随趋势延续逐渐增大，使SAR加速靠近价格',en:'1. In uptrend, SAR tracks below price\n2. When price breaks below SAR, trend flips, SAR moves above price\n3. AF increases as trend extends, accelerating SAR toward price'},
    signals:{zh:[['点在价格下方','上升趋势','持多，SAR即止损位','pos'],['点从上方跳到下方','买入信号','趋势由空转多','pos'],['点在价格上方','下降趋势','持空，SAR即止损位','neg'],['点从下方跳到上方','卖出信号','趋势由多转空','neg']],
              en:[['Dots below price','Uptrend active','Stay long, SAR is stop-loss','pos'],['Dots flip from above to below','Buy signal','Trend turns bullish','pos'],['Dots above price','Downtrend active','Stay short, SAR is stop-loss','neg'],['Dots flip from below to above','Sell signal','Trend turns bearish','neg']]}
  },
  RSI: {
    fullName:{zh:'RSI — 相对强弱指数 (14期)',en:'RSI — Relative Strength Index (14)'},
    desc:{zh:'通过比较一定时期内的平均涨跌幅度，衡量价格动能的强弱，识别超买超卖区域。',en:'Measures price momentum by comparing average gains vs losses over a period, identifying overbought and oversold conditions.'},
    formula:{zh:'RSI = 100 − 100 / (1 + RS)\nRS = 14日平均涨幅 / 14日平均跌幅',en:'RSI = 100 − 100 / (1 + RS)\nRS = Avg Gain (14) / Avg Loss (14)'},
    calc:{zh:'1. 计算每日收盘价变动\n2. 分别平均14日内的上涨和下跌幅度\n3. RS = 平均涨幅 / 平均跌幅\n4. 代入公式得RSI（范围0–100）',en:'1. Calculate daily price changes\n2. Average gains and losses separately over 14 periods\n3. RS = Avg Gain / Avg Loss\n4. Apply formula to get RSI (range 0–100)'},
    signals:{zh:[['RSI > 70','超买区','警惕回调，考虑减仓','neg'],['RSI 50–70','强势多头','上涨动能充足','pos'],['RSI 30–50','弱势偏空','观望或轻仓',''],['RSI < 30','超卖区','关注反弹，关注底部信号','pos']],
              en:[['RSI > 70','Overbought','Watch for pullback, consider reducing','neg'],['RSI 50–70','Strong bullish','Upward momentum healthy','pos'],['RSI 30–50','Weak/bearish','Watch or light position',''],['RSI < 30','Oversold','Watch for bounce, look for base','pos']]}
  },
  KDJ: {
    fullName:{zh:'KDJ — 随机指标',en:'KDJ — Stochastic Oscillator'},
    desc:{zh:'通过比较收盘价与一段时间内高低价的关系来衡量动能，J线具有高敏感度可提前预警。',en:'Measures momentum by comparing close to the high-low range over a period. The J line is highly sensitive and provides early warning signals.'},
    formula:{zh:'RSV = (C − 9日最低) / (9日最高 − 9日最低) × 100\nK = 2/3 × K₋₁ + 1/3 × RSV\nD = 2/3 × D₋₁ + 1/3 × K\nJ = 3K − 2D',en:'RSV = (Close − 9-day Low) / (9-day High − 9-day Low) × 100\nK = 2/3 × Prev K + 1/3 × RSV\nD = 2/3 × Prev D + 1/3 × K\nJ = 3K − 2D'},
    calc:{zh:'RSV（原始随机值）反映收盘价在9日区间内的位置，K和D是对RSV的平滑，J线是K和D的超前量，波动范围通常超过0–100。',en:'RSV (raw stochastic) shows where close sits in the 9-day range. K and D are smoothed RSV. J line leads K and D, often oscillating beyond 0–100.'},
    signals:{zh:[['K值 > 80','超买区','J线若同步高于100，注意反转','neg'],['K值上穿D值','金叉买入','','pos'],['K值 < 20','超卖区','J线若低于0，注意反弹','pos'],['K值下穿D值','死叉卖出','','neg']],
              en:[['K > 80','Overbought zone','If J > 100 simultaneously, watch reversal','neg'],['K crosses above D','Golden cross, buy','','pos'],['K < 20','Oversold zone','If J < 0, watch bounce','pos'],['K crosses below D','Death cross, sell','','neg']]}
  },
  CCI: {
    fullName:{zh:'CCI — 顺势指标',en:'CCI — Commodity Channel Index'},
    desc:{zh:'衡量价格是否偏离统计正常范围，对于捕捉价格的波段拐点非常灵敏，在震荡市中表现尤为突出。',en:'Measures how far price has deviated from its statistical norm. Highly sensitive to swing turning points, especially effective in ranging markets.'},
    formula:{zh:'CCI = (典型价格 − SMA(20)) / (0.015 × 平均绝对偏差)\n典型价格 = (最高 + 最低 + 收盘) / 3',en:'CCI = (Typical Price − SMA(20)) / (0.015 × Mean Deviation)\nTypical Price = (High + Low + Close) / 3'},
    calc:{zh:'1. 计算典型价格TP\n2. 计算TP的20日SMA\n3. 计算TP与SMA的平均绝对偏差\n4. 代入公式，0.015是使约70%的数据落在±100范围内的修正常数',en:'1. Calculate Typical Price (TP)\n2. Compute 20-period SMA of TP\n3. Calculate mean absolute deviation of TP from SMA\n4. Apply formula; 0.015 keeps ~70% of values within ±100'},
    signals:{zh:[['CCI > +100','价格偏高于正常范围','超买，可能回落','neg'],['CCI 0 至 +100','正常偏强区间','温和看多','pos'],['CCI -100 至 0','正常偏弱区间','温和看空',''],['CCI < -100','价格偏低于正常范围','超卖，可能反弹','pos']],
              en:[['CCI > +100','Price above normal range','Overbought, may pull back','neg'],['CCI 0 to +100','Normal bullish zone','Mildly bullish','pos'],['CCI -100 to 0','Normal bearish zone','Mildly bearish',''],['CCI < -100','Price below normal range','Oversold, may bounce','pos']]}
  },
  WILLR: {
    fullName:{zh:'威廉指标 %R',en:'Williams %R'},
    desc:{zh:'反映收盘价在过去N个周期高低区间内的相对位置，是KDJ的倒置版，对超买超卖的反应极为灵敏。',en:'Reflects the close\'s position within the N-period high-low range. An inverted version of Stochastics, extremely sensitive to overbought/oversold conditions.'},
    formula:{zh:'%R = −(N日最高 − 收盘价) / (N日最高 − N日最低) × 100\n（范围：-100 到 0）',en:'%R = −(N-day High − Close) / (N-day High − N-day Low) × 100\n(Range: -100 to 0)'},
    calc:{zh:'取最近14日的最高价和最低价，计算当前收盘价在该区间内的位置，结果乘以-1使值为负数区间，便于与其他指标区分。',en:'Take the highest high and lowest low of the last 14 periods. Calculate where the current close sits within that range, multiplied by -1 for a negative scale.'},
    signals:{zh:[['%R 0 至 -20','严重超买区','注意回调风险','neg'],['%R -20 至 -50','多头区间','趋势较强','pos'],['%R -50 至 -80','空头区间','趋势较弱',''],['%R -80 至 -100','严重超卖区','关注反弹信号','pos']],
              en:[['%R 0 to -20','Severely overbought','Watch for pullback','neg'],['%R -20 to -50','Bullish zone','Trend relatively strong','pos'],['%R -50 to -80','Bearish zone','Trend relatively weak',''],['%R -80 to -100','Severely oversold','Watch for bounce signal','pos']]}
  },
  ROC: {
    fullName:{zh:'ROC — 变动率指标',en:'ROC — Rate of Change'},
    desc:{zh:'通过计算当前收盘价与N日前价格的百分比变化，监测价格运动的速度和动能。',en:'Monitors the speed and momentum of price movement by calculating the percentage change between current close and the close N periods ago.'},
    formula:{zh:'ROC = (当前收盘 − N日前收盘) / N日前收盘 × 100%\n（默认N = 10）',en:'ROC = (Current Close − Close N periods ago) / Close N periods ago × 100%\n(Default N = 10)'},
    calc:{zh:'直接比较当前价与10日前价格的百分比差异，正值代表价格上涨，负值代表下跌，数值大小反映变动速度。',en:'Directly compares current price to the price 10 periods ago as a percentage. Positive = rising, negative = falling; magnitude reflects speed.'},
    signals:{zh:[['ROC > +3%','强劲上涨动能','趋势加速，可追多','pos'],['ROC 0 至 +3%','温和上涨','稳健多头','pos'],['ROC -3% 至 0','温和下跌','偏空观望','neg'],['ROC < -3%','强劲下跌动能','趋势加速向下，谨慎','neg']],
              en:[['ROC > +3%','Strong upward momentum','Trend accelerating, buy momentum','pos'],['ROC 0 to +3%','Mild upside','Steady bull','pos'],['ROC -3% to 0','Mild downside','Lean bearish','neg'],['ROC < -3%','Strong downward momentum','Trend accelerating down, caution','neg']]}
  },
  BOLL: {
    fullName:{zh:'布林带 — Bollinger Bands',en:'Bollinger Bands'},
    desc:{zh:'以20日均线为中轨，上下各加减2倍标准差形成上下轨，利用统计学的方法量化价格的波动率。',en:'Uses a 20-day MA as the middle band, with upper and lower bands at ±2 standard deviations. Quantifies price volatility using statistical methods.'},
    formula:{zh:'中轨 = SMA(20)\n上轨 = SMA(20) + 2σ\n下轨 = SMA(20) − 2σ\nσ = 20日收盘价标准差',en:'Middle = SMA(20)\nUpper = SMA(20) + 2σ\nLower = SMA(20) − 2σ\nσ = Standard deviation of 20-day closes'},
    calc:{zh:'1. 计算20日收盘价的简单移动平均作为中轨\n2. 计算20日收盘价的标准差σ\n3. 中轨上下各加减2σ得到上下轨\n4. 约95%的价格将落在上下轨之间',en:'1. Calculate 20-day SMA as middle band\n2. Calculate standard deviation σ of 20 closes\n3. Add/subtract 2σ from middle for upper/lower bands\n4. ~95% of prices will fall within the bands'},
    signals:{zh:[['价格触及上轨','相对超买','均值回归可能，注意做空机会','neg'],['布林带收窄（挤压）','低波动，大行情蓄势','突破方向即为趋势方向',''],['价格触及下轨','相对超卖','反弹概率增加','pos'],['价格突破上轨且带变宽','强势突破','动能充足的上涨行情','pos']],
              en:[['Price at upper band','Relatively overbought','Mean reversion likely, watch for short','neg'],['Bands squeeze together','Low volatility, big move brewing','Breakout direction = trend direction',''],['Price at lower band','Relatively oversold','Bounce probability rising','pos'],['Price breaks upper band + bands widen','Strong breakout','High-momentum uptrend','pos']]}
  },
  ATR: {
    fullName:{zh:'ATR — 平均真实波幅',en:'ATR — Average True Range'},
    desc:{zh:'衡量市场真实波动幅度的指标，不代表价格方向，主要用于设置动态止损和评估市场风险。',en:'Measures the true range of market movement without indicating direction. Primarily used for setting dynamic stop-losses and assessing market risk.'},
    formula:{zh:'TR = max(日内高低差, |当日最高 − 前日收盘|, |当日最低 − 前日收盘|)\nATR(14) = EMA(TR, 14)',en:'TR = max(High − Low, |High − Prev Close|, |Low − Prev Close|)\nATR(14) = EMA(TR, 14)'},
    calc:{zh:'真实波幅TR考虑了跳空缺口的影响，是比日内高低差更准确的波动度量。对TR进行14日指数平均得到ATR，数值越大波动越剧烈。',en:'True Range accounts for gap opens, making it more accurate than just High-Low. EMA of TR over 14 periods gives ATR. Higher ATR = more volatile market.'},
    signals:{zh:[['ATR/价格 > 2%','高波动市场','扩大止损距离，降低仓位','neg'],['ATR/价格 1–2%','正常波动','标准止损设置',''],['ATR/价格 < 1%','低波动市场','关注即将到来的趋势行情','pos'],['止损设置','买入价 − 2×ATR','动态跟随市场波动调整止损','']],
              en:[['ATR/Price > 2%','High volatility','Widen stops, reduce position size','neg'],['ATR/Price 1–2%','Normal volatility','Standard stop placement',''],['ATR/Price < 1%','Low volatility','Watch for upcoming trend move','pos'],['Stop placement','Entry − 2×ATR','Dynamic stop follows market volatility','']]}
  },
  KELTNER: {
    fullName:{zh:'肯特纳通道 — Keltner Channel',en:'Keltner Channel'},
    desc:{zh:'类似布林带，但以ATR而非标准差构建通道，线条更平滑，能有效过滤假突破噪音。',en:'Similar to Bollinger Bands but uses ATR instead of standard deviation. Smoother lines that more effectively filter false breakout noise.'},
    formula:{zh:'中轨 = EMA(20)\n上轨 = EMA(20) + 2 × ATR(14)\n下轨 = EMA(20) − 2 × ATR(14)',en:'Middle = EMA(20)\nUpper = EMA(20) + 2 × ATR(14)\nLower = EMA(20) − 2 × ATR(14)'},
    calc:{zh:'使用EMA而非SMA作为中轨，赋予近期价格更大权重；用ATR作为通道宽度，使其动态反映当前市场波动率，相比布林带更能适应趋势行情。',en:'Uses EMA (not SMA) as the middle, giving recent prices more weight. ATR-based width dynamically adapts to current volatility, making it better suited for trending markets than Bollinger.'},
    signals:{zh:[['价格突破上轨','强势上涨信号','顺势做多','pos'],['价格在中轨上方运行','多头趋势中','上涨动能持续','pos'],['价格跌破下轨','弱势下跌信号','顺势做空或止损','neg'],['价格穿越中轨','趋势可能转变','等待确认','']],
              en:[['Price breaks above upper','Strong bullish signal','Trend-follow long','pos'],['Price runs above middle','Bullish trend intact','Upward momentum continues','pos'],['Price breaks below lower','Weak bearish signal','Short or stop out','neg'],['Price crosses middle band','Trend may be shifting','Wait for confirmation','']]}
  },
  VOLUME: {
    fullName:{zh:'成交量比 — Volume Ratio',en:'Volume Ratio vs Average'},
    desc:{zh:'将当日成交量与近20日平均成交量相比，量比是判断价格行情的重要辅助工具。',en:'Compares current volume to the 20-day average. Volume ratio is an important supplementary tool for confirming price moves.'},
    formula:{zh:'量比 = 当日成交量 / 20日平均成交量',en:'Volume Ratio = Current Volume / 20-Day Average Volume'},
    calc:{zh:'计算过去20个交易日的平均成交量，将当日量除以该均值，大于1表示放量，小于1表示缩量。',en:'Calculate average volume over the last 20 trading days. Divide today\'s volume by that average. >1 = expanding volume, <1 = contracting volume.'},
    signals:{zh:[['量比 > 2','放量','大资金介入，关注方向','pos'],['量比 1–2','温和放量','正常买卖','pos'],['量比 0.5–1','缩量','观望情绪浓，方向不明',''],['量比 < 0.5','极度缩量','流动性不足，慎入','neg']],
              en:[['Ratio > 2','Volume surge','Big money active, watch direction','pos'],['Ratio 1–2','Mild expansion','Normal buying/selling','pos'],['Ratio 0.5–1','Shrinking','Wait-and-see mode, direction unclear',''],['Ratio < 0.5','Extremely thin','Low liquidity, be cautious','neg']]}
  },
  OBV: {
    fullName:{zh:'OBV — 能量潮指标',en:'OBV — On-Balance Volume'},
    desc:{zh:'将成交量累积化，价格上涨时加入成交量，下跌时减去成交量，通过量价关系研判机构动向。',en:'Cumulates volume: adds volume on up days, subtracts on down days. Studies institutional behavior through volume-price relationships.'},
    formula:{zh:'若当日收盘 > 前日收盘：OBV = OBV₋₁ + 成交量\n若当日收盘 < 前日收盘：OBV = OBV₋₁ − 成交量\n若相等：OBV = OBV₋₁',en:'If Close > Prev Close: OBV = Prev OBV + Volume\nIf Close < Prev Close: OBV = Prev OBV − Volume\nIf Equal: OBV = Prev OBV'},
    calc:{zh:'OBV理论认为，机构在推高价格前会先悄悄买入（放量上涨），在出货前先悄悄卖出（放量下跌），因此OBV的变化往往领先价格。',en:'OBV theory: institutions accumulate quietly before pushing price up (volume on up days) and distribute before a drop (volume on down days). OBV changes often lead price.'},
    signals:{zh:[['OBV与价格同步创新高','量价配合','上涨趋势健康','pos'],['价格创新高但OBV不创新高','顶背离','上涨动能枯竭，看跌信号','neg'],['OBV与价格同步创新低','量价配合','下跌趋势延续','neg'],['价格创新低但OBV不创新低','底背离','下跌动能减弱，看涨信号','pos']],
              en:[['OBV new high with price','Volume confirms','Healthy uptrend','pos'],['Price new high but OBV lower','Bearish divergence','Upward momentum exhausted, bearish signal','neg'],['OBV new low with price','Volume confirms','Downtrend continues','neg'],['Price new low but OBV higher','Bullish divergence','Downward momentum weakening, bullish signal','pos']]}
  },
  CMF: {
    fullName:{zh:'CMF — 蔡金货币流量指标',en:'CMF — Chaikin Money Flow'},
    desc:{zh:'通过收盘价在当日高低范围内的位置和成交量，衡量一段时间内的资金净流入还是净流出。',en:'Uses the close\'s position within the daily high-low range weighted by volume to measure net capital inflow or outflow over a period.'},
    formula:{zh:'资金流量乘数 = [(C−L) − (H−C)] / (H−L)\n资金流量体积 = 乘数 × 成交量\nCMF = Σ(资金流量体积) / Σ(成交量)  （20日）',en:'Money Flow Multiplier = [(C−L) − (H−C)] / (H−L)\nMoney Flow Volume = Multiplier × Volume\nCMF = Σ(MFV) / Σ(Volume)  (20-period)'},
    calc:{zh:'资金流量乘数反映收盘价在当日区间内靠近上方（+1）还是下方（-1）的程度，乘以成交量后累积，再除以总成交量归一化。',en:'The multiplier measures how close the close is to the top (+1) or bottom (-1) of the daily range. Weighted by volume, summed, and normalized by total volume.'},
    signals:{zh:[['CMF > +0.25','强势资金流入','机构持续买入','pos'],['CMF 0 至 +0.25','资金净流入','温和看多','pos'],['CMF -0.25 至 0','资金净流出','温和看空','neg'],['CMF < -0.25','强势资金流出','机构持续卖出','neg']],
              en:[['CMF > +0.25','Strong inflow','Institutions actively buying','pos'],['CMF 0 to +0.25','Net inflow','Mildly bullish','pos'],['CMF -0.25 to 0','Net outflow','Mildly bearish','neg'],['CMF < -0.25','Strong outflow','Institutions actively selling','neg']]}
  },
  FIB: {
    fullName:{zh:'斐波那契回撤 — Fibonacci Retracement',en:'Fibonacci Retracement'},
    desc:{zh:'基于斐波那契数列，将市场的一段涨跌区间划分为0%、23.6%、38.2%、50%、61.8%、100%等关键水平，用于预判支撑阻力。',en:'Based on the Fibonacci sequence, divides a price swing into 0%, 23.6%, 38.2%, 50%, 61.8%, 100% levels to predict support and resistance.'},
    formula:{zh:'回撤位 = 高点 − (高点 − 低点) × 斐波那契比率\n关键比率：0.236, 0.382, 0.5, 0.618, 0.786',en:'Retracement Level = High − (High − Low) × Fibonacci Ratio\nKey ratios: 0.236, 0.382, 0.5, 0.618, 0.786'},
    calc:{zh:'1. 确定一段明显趋势的高点和低点\n2. 用高低点的价格差乘以各斐波那契比率\n3. 从高点减去该值得到回撤支撑位（上涨后回调）\n4. 0.618被称为"黄金分割"，是最重要的支撑位',en:'1. Identify high and low of a significant trend\n2. Multiply the price range by each Fibonacci ratio\n3. Subtract from high to get retracement support levels\n4. 0.618 ("golden ratio") is the most significant support level'},
    signals:{zh:[['价格在61.8%附近支撑','黄金分割支撑','强支撑，适合做多','pos'],['价格在38.2%附近','重要回撤位','中度支撑，可轻仓','pos'],['价格跌破50%','心理关口破位','趋势或延续回调','neg'],['价格跌破61.8%','黄金分割失守','趋势反转风险增大','neg']],
              en:[['Price holds near 61.8%','Golden ratio support','Strong support, good long entry','pos'],['Price near 38.2%','Key retracement','Moderate support, light entry','pos'],['Price breaks 50%','Psychological level broken','Pullback may extend','neg'],['Price breaks 61.8%','Golden ratio lost','Trend reversal risk increases','neg']]}
  },
  SR: {
    fullName:{zh:'支撑阻力位 — Support & Resistance',en:'Support & Resistance Levels'},
    desc:{zh:'基于近期价格的高低点，动态计算当前市场的关键支撑和阻力价位，是最基础也最重要的技术分析工具。',en:'Dynamically calculates key support and resistance price levels from recent highs and lows. The most fundamental and important technical analysis tool.'},
    formula:{zh:'阻力位 = 近20日最高收盘价附近\n支撑位 = 近20日最低收盘价附近\n突破确认需要收盘价站稳关键位上方/下方',en:'Resistance ≈ Near recent 20-day high close\nSupport ≈ Near recent 20-day low close\nBreakout confirmed by close above/below the level'},
    calc:{zh:'支撑位是价格多次下跌后反弹的区域，代表买方力量聚集；阻力位是价格多次上涨后回落的区域，代表卖方力量聚集。当关键位被突破时，原支撑位变阻力位，反之亦然。',en:'Support is where price bounces repeatedly (buyers accumulate). Resistance is where price falls repeatedly (sellers accumulate). When a key level breaks, support becomes resistance and vice versa.'},
    signals:{zh:[['价格靠近支撑位','关键买入区域','止损设在支撑位下方','pos'],['价格有效突破阻力位','阻力转支撑','追涨介入，目标看下一阻力位','pos'],['价格靠近阻力位','关键卖出区域','止损设在阻力位上方','neg'],['价格跌破支撑位','支撑转阻力','止损离场，目标看下一支撑','neg']],
              en:[['Price near support','Key buy zone','Stop-loss below support','pos'],['Price breaks resistance cleanly','Resistance becomes support','Enter on breakout, target next resistance','pos'],['Price near resistance','Key sell zone','Stop-loss above resistance','neg'],['Price breaks below support','Support becomes resistance','Stop out, target next support','neg']]}
  },
};

// ── Build indicator panel HTML ────────────────────────────────────
export function buildIndicatorsPanel(vals={}, lang='zh') {
  return `
  <div class="ind-v2-wrap">
    ${IND_GROUPS.map(g=>`
    <div class="ind-group">
      <div class="ind-group-hd">
        <span>${lang==='zh'?g.zh:g.en}</span>
      </div>
      ${g.items.map(key=>{
        const meta=IND_META[key]||{zh:key,en:key,icon:'•'};
        const v=vals[key]||{};
        const sig=SIG_CFG[v.signal]||SIG_CFG.neutral;
        const valCls=v.signal==='bullish'||v.signal==='stable'?'pos':v.signal==='bearish'||v.signal==='volatile'?'neg':'';
        return `
        <div class="ind-row-v2" data-ikey="${key}">
          <span class="ind-v2-icon">${meta.icon}</span>
          <span class="ind-v2-name">${lang==='zh'?meta.zh:meta.en}</span>
          <span class="ind-v2-val ${valCls}">${v.display||'—'}</span>
          <span class="ind-sig ${sig.cls}">${lang==='zh'?sig.zh:sig.en}</span>
          <span class="ind-v2-arr">›</span>
        </div>`;
      }).join('')}
    </div>`).join('')}
  </div>`;
}

// ── Show indicator detail modal ───────────────────────────────────
export function showIndicatorModal(key, vals, candles, lang) {
  // Remove existing modal
  document.querySelector('.ind-modal-wrap')?.remove();

  const meta = IND_META[key]||{zh:key,en:key,icon:'•'};
  const detail = IND_DETAIL[key];
  const v = vals[key]||{};
  const sig = SIG_CFG[v.signal]||SIG_CFG.neutral;
  const L = lang||'zh';

  const wrap = document.createElement('div');
  wrap.className = 'ind-modal-wrap';
  wrap.innerHTML = `
  <div class="ind-modal-bd"></div>
  <div class="ind-modal-panel">
    <div class="ind-modal-hd">
      <div style="display:flex;align-items:center;gap:12px">
        <span style="font-size:28px">${meta.icon}</span>
        <div>
          <div class="ind-modal-title">${detail?(L==='zh'?detail.fullName.zh:detail.fullName.en):(L==='zh'?meta.zh:meta.en)}</div>
          <div style="display:flex;align-items:center;gap:10px;margin-top:4px">
            <span class="ind-modal-curval">${v.display||'—'}</span>
            <span class="ind-sig ${sig.cls}" style="font-size:11px">${L==='zh'?sig.zh:sig.en}</span>
          </div>
        </div>
      </div>
      <button class="ind-modal-close" id="ind-modal-close">✕</button>
    </div>
    <div class="ind-modal-body">
      ${detail?`
      <!-- Description -->
      <div class="ind-section">
        <p class="ind-desc">${L==='zh'?detail.desc.zh:detail.desc.en}</p>
      </div>
      <!-- Formula -->
      <div class="ind-section">
        <div class="ind-section-title">${L==='zh'?'📐 计算公式':'📐 Formula'}</div>
        <div class="ind-formula">${(L==='zh'?detail.formula.zh:detail.formula.en).replace(/\n/g,'<br>')}</div>
      </div>
      <!-- Calculation -->
      <div class="ind-section">
        <div class="ind-section-title">${L==='zh'?'🔢 计算步骤':'🔢 How It\'s Calculated'}</div>
        <div class="ind-calc">${(L==='zh'?detail.calc.zh:detail.calc.en).replace(/\n/g,'<br>')}</div>
      </div>
      <!-- Chart -->
      <div class="ind-section">
        <div class="ind-section-title">${L==='zh'?'📈 指标走势':'📈 Indicator Chart'}</div>
        <canvas id="ind-modal-canvas" class="ind-modal-canvas"></canvas>
      </div>
      <!-- Signals table -->
      <div class="ind-section">
        <div class="ind-section-title">${L==='zh'?'🎯 信号解读':'🎯 Signal Interpretation'}</div>
        <div class="ind-signal-table">
          ${(L==='zh'?detail.signals.zh:detail.signals.en).map(([range,label,action,cls])=>`
          <div class="ind-sig-row ${cls?'ind-sig-row--'+cls:''}">
            <span class="ind-sig-range">${range}</span>
            <span class="ind-sig-label">${label}</span>
            <span class="ind-sig-action">${action}</span>
          </div>`).join('')}
        </div>
      </div>` : `<div class="ind-section"><p class="ind-desc">${L==='zh'?'详细信息即将添加':'Details coming soon.'}</p></div>`}
    </div>
  </div>`;

  document.body.appendChild(wrap);
  requestAnimationFrame(()=>wrap.classList.add('ind-modal-visible'));

  // Close
  const close = () => { wrap.classList.remove('ind-modal-visible'); setTimeout(()=>wrap.remove(),320); };
  wrap.querySelector('#ind-modal-close').onclick = close;
  wrap.querySelector('.ind-modal-bd').onclick = close;

  // Draw chart
  if (candles && candles.length > 5) {
    setTimeout(()=>drawModalChart(key, vals, candles), 80);
  }
}

function drawModalChart(key, vals, candles) {
  const canvas = document.querySelector('#ind-modal-canvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio||1;
  const W = canvas.offsetWidth||500, H = 120;
  canvas.width = W*dpr; canvas.height = H*dpr;
  canvas.style.width = W+'px'; canvas.style.height = H+'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr,dpr);

  const meta = IND_META[key]||{};
  const v = vals[key]||{};
  const C = candles.map(c=>c.c);
  const H2 = candles.map(c=>c.h);
  const L2 = candles.map(c=>c.l);
  const pad=10, n=candles.length;

  function drawLine(series, color, lineW=1.5) {
    const valid = series.filter(v=>v!=null);
    if(!valid.length)return;
    const mn=Math.min(...valid), mx=Math.max(...valid);
    const range=mx-mn||1;
    const pY=v=>pad+(H-2*pad)*(1-(v-mn)/range);
    ctx.beginPath();
    let first=true;
    series.forEach((val,i)=>{
      if(val==null)return;
      const x=pad+i*(W-2*pad)/(n-1);
      first?ctx.moveTo(x,pY(val)):ctx.lineTo(x,pY(val));
      first=false;
    });
    ctx.strokeStyle=color; ctx.lineWidth=lineW; ctx.stroke();
  }

  function drawHLine(y, color) {
    ctx.beginPath(); ctx.moveTo(pad,y); ctx.lineTo(W-pad,y);
    ctx.strokeStyle=color; ctx.lineWidth=0.5; ctx.setLineDash([3,4]); ctx.stroke(); ctx.setLineDash([]);
  }

  ctx.clearRect(0,0,W,H);
  ctx.fillStyle='rgba(6,13,31,0.6)'; ctx.fillRect(0,0,W,H);

  const type = meta.chartType;

  if(type==='oscillator') {
    // Attempt to get series data
    let series=null;
    if(key==='RSI' && v.series) series=v.series;
    else if(key==='CCI' && v.series) series=v.series;
    else if(key==='ROC' && v.series) series=v.series;
    else {
      // generate approximate oscillator from RSI
      series = vals.RSI?.series || null;
    }
    if(!series) { drawLine(C,'#60a5fa'); return; }
    const valid=series.filter(v=>v!=null);
    const mn=Math.min(...valid,0), mx=Math.max(...valid,100);
    const range=mx-mn||1;
    const pY=v=>pad+(H-2*pad)*(1-(v-mn)/range);
    // zones
    if(key==='RSI'){
      ctx.fillStyle='rgba(255,61,87,0.08)';
      ctx.fillRect(pad,pad,(W-2*pad),(H-2*pad)*(1-70/100));
      ctx.fillStyle='rgba(0,255,136,0.08)';
      ctx.fillRect(pad,pY(30),(W-2*pad),H-2*pad-pY(30));
      drawHLine(pY(70),'rgba(255,61,87,0.3)');
      drawHLine(pY(50),'rgba(255,255,255,0.1)');
      drawHLine(pY(30),'rgba(0,255,136,0.3)');
    }
    drawLine(series,'#60a5fa');
    // mark current value
    const lastVal=series[series.length-1];
    if(lastVal!=null){
      const x=W-pad, y=pY(lastVal);
      ctx.beginPath(); ctx.arc(x,y,4,0,Math.PI*2);
      ctx.fillStyle='#60a5fa'; ctx.fill();
    }
  } else if(type==='macd') {
    if(!v.hist) { drawLine(C,'#60a5fa'); return; }
    const hist=v.hist;
    const valid=hist.filter(v=>v!=null);
    if(!valid.length)return;
    const absMax=Math.max(...valid.map(Math.abs));
    const pY=v=>H/2-(v/absMax)*(H/2-pad);
    // zero line
    drawHLine(H/2,'rgba(255,255,255,0.15)');
    // histogram bars
    const bW=(W-2*pad)/n*0.8;
    hist.forEach((val,i)=>{
      if(val==null)return;
      const x=pad+i*(W-2*pad)/n;
      const y0=H/2, y1=pY(val);
      ctx.fillStyle=val>=0?'rgba(0,255,136,0.5)':'rgba(255,61,87,0.5)';
      ctx.fillRect(x,Math.min(y0,y1),bW,Math.abs(y1-y0)||1);
    });
    // MACD line
    if(v.macdLine) drawLine(v.macdLine,'#60a5fa',1);
    if(v.signalLine) drawLine(v.signalLine,'#fbbf24',1);
  } else {
    // Default: price line
    drawLine(C,'#60a5fa');
  }
}
