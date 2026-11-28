#!/usr/bin/env python3
"""Genera il bollettino operativo CommandChatGPT dai cinque repository ufficiali."""
import json, urllib.request, datetime as dt, statistics, os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
URLS = {
 "ARRotation": "https://raw.githubusercontent.com/Giorgiogoldoni/arrotation/main/data/rotation.json",
 "Flussi ETFIQ": "https://raw.githubusercontent.com/Giorgiogoldoni/arrotation/main/data/flows.json",
 "Selezione ARRotation": "https://raw.githubusercontent.com/Giorgiogoldoni/arrotation/main/data/selezione.json",
 "BIGCHATGPT": "https://giorgiogoldoni.github.io/BIGCHATGPT/data/index.json",
 "GeografiaChatGPT": "https://raw.githubusercontent.com/Giorgiogoldoni/geografiachatgpt/main/geografia-motore.json",
 "Geografia UCITS": "https://raw.githubusercontent.com/Giorgiogoldoni/geografiachatgpt/main/ucits_geography.json",
 "SniperChatGPT": "https://raw.githubusercontent.com/Giorgiogoldoni/sniperchatgpt/main/reports/current_signals.json",
 "Sniper RRG": "https://raw.githubusercontent.com/Giorgiogoldoni/sniperchatgpt/main/reports/sniper_rrg_summary.json",
 "FactorChatGPT RRG": "https://raw.githubusercontent.com/Giorgiogoldoni/Factorchatgpt/main/data/rrg.json",
 "TAX snapshot": "https://raw.githubusercontent.com/Giorgiogoldoni/TAX-ETP-MANAGER/main/data/market_snapshot.json",
 "TAX storico": "https://raw.githubusercontent.com/Giorgiogoldoni/TAX-ETP-MANAGER/main/data/history.json",
 "TAX strategia": "https://raw.githubusercontent.com/Giorgiogoldoni/TAX-ETP-MANAGER/main/data/strategy.json",
 "TAX strumenti": "https://raw.githubusercontent.com/Giorgiogoldoni/TAX-ETP-MANAGER/main/data/instruments.json",
 "TAX watchlist": "https://raw.githubusercontent.com/Giorgiogoldoni/TAX-ETP-MANAGER/main/data/watchlist.json",
 "TAX portafoglio": "https://raw.githubusercontent.com/Giorgiogoldoni/TAX-ETP-MANAGER/main/data/portfolio.json",
}
def fetch(name, url):
    try:
        req=urllib.request.Request(url, headers={"User-Agent":"CommandChatGPT-Bollettino/1.0","Cache-Control":"no-cache"})
        with urllib.request.urlopen(req, timeout=35) as r: return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("FEED ERROR", name, repr(e))
        return None
def parse_date(s):
    if not s: return None
    raw=str(s).strip()
    if raw.endswith(" UTC"): raw=raw[:-4].strip()+"+00:00"
    raw=raw.replace("Z","+00:00")
    if "T" not in raw and " " in raw: raw=raw.replace(" ","T",1)
    try:
        parsed=dt.datetime.fromisoformat(raw)
        if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        try: return dt.datetime.strptime(str(s),"%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        except Exception: return None
def age_days(s):
    d=parse_date(s)
    return (dt.datetime.now(dt.timezone.utc)-d).total_seconds()/86400 if d else None
def safe_num(v):
    try: return float(v) if v is not None else None
    except Exception: return None
def fetch_yahoo_benchmark(symbol="ACWI.MI"):
    try:
        end=int(dt.datetime.now(dt.timezone.utc).timestamp()); start=end-370*86400
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start}&period2={end}&interval=1d&events=div%2Csplits"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 CommandChatGPT/1.0"})
        with urllib.request.urlopen(req,timeout=20) as response: payload=json.loads(response.read().decode("utf-8"))
        result=payload["chart"]["result"][0]; stamps=result.get("timestamp",[]) or []
        indicators=result.get("indicators",{}); adj=(indicators.get("adjclose") or [{}])[0].get("adjclose") or []
        close=(indicators.get("quote") or [{}])[0].get("close") or []; values=[]
        for i,stamp in enumerate(stamps):
            value=adj[i] if i<len(adj) and adj[i] is not None else (close[i] if i<len(close) else None)
            if value is not None and float(value)>0: values.append((int(stamp),float(value)))
        if len(values)<130: return None
        latest=values[-1][1]
        def ret(n): return round((latest/values[-(n+1)][1]-1)*100,2) if len(values)>n else None
        return {"symbol":symbol,"name":"Amundi MSCI All Country World UCITS ETF EUR Acc","isin":"LU1829220216",
                "price":round(latest,5),"price_date":dt.datetime.fromtimestamp(values[-1][0],dt.timezone.utc).date().isoformat(),
                "trailing_1m_pct":ret(21),"trailing_3m_pct":ret(63),"trailing_6m_pct":ret(126),
                "source":"Yahoo Finance adjusted close","currency":(result.get("meta") or {}).get("currency")}
    except Exception as e:
        print("BENCHMARK ERROR",repr(e)); return None
def fetch_ticker_daily(symbol,days=370):
    try:
        end=int(dt.datetime.now(dt.timezone.utc).timestamp()); start=end-days*86400
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start}&period2={end}&interval=1d"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 CommandChatGPT/1.0"})
        with urllib.request.urlopen(req,timeout=12) as response: payload=json.loads(response.read().decode("utf-8"))
        result=payload["chart"]["result"][0]
        stamps=result.get("timestamp",[]) or []
        closes=(result.get("indicators",{}).get("quote") or [{}])[0].get("close") or []
        values=[(dt.datetime.fromtimestamp(stamps[i],dt.timezone.utc).date().isoformat(),float(closes[i])) for i in range(min(len(stamps),len(closes))) if closes[i] is not None and float(closes[i])>0]
        if len(values)<200: return None
        prices=[x[1] for x in values]; last=prices[-1]; ma200=sum(prices[-200:])/200
        roc38=(last/prices[-39]-1)*100 if len(prices)>=39 else None
        gap=(last/ma200-1)*100
        low=ma200*1.02; high=ma200*1.05
        entry=("ZONA INGRESSO" if 2<=gap<=5 else "ATTENDERE CONSOLIDAMENTO" if 0<gap<2 else "ATTENDERE RITRACCIAMENTO" if 5<gap<=8 else "NON INSEGUIRE" if gap>8 else "SOTTO SMA200")
        return {"ticker":symbol,"last_price":round(last,4),"last_date":values[-1][0],"sma200":round(ma200,4),"gap_sma200_pct":round(gap,2),"roc38_pct":round(roc38,2) if roc38 is not None else None,"entry_zone_low":round(low,4),"entry_zone_high":round(high,4),"entry_status":entry,"above_sma200":last>ma200,"trend_momentum":last>ma200 and (roc38 or -999)>0}
    except Exception as e:
        print("ETF CANDIDATE ERROR",symbol,repr(e)); return None
def build_sector_theme_candidates(categories,rrg_data,big_rows,big_stale):
    # Shortlist per strength category; ticker data individually validated via Yahoo daily history.
    top=[x for x in categories if x.get("group") in ("Settori","Temi") and (safe_num(x.get("rel20")) or 0)>0]
    top.sort(key=lambda x:safe_num(x.get("score")) if safe_num(x.get("score")) is not None else -1e9,reverse=True)
    symbols=[]
    for category in top[:8]:
        for ticker in (category.get("tickers") or [])[:3]:
            if ticker not in symbols: symbols.append(ticker)
    rrgmap={str(a.get("ticker","")).upper():a for a in (rrg_data.get("assets") or [])}
    results=[]
    for ticker in symbols[:24]:
        quote=fetch_ticker_daily(ticker)
        if not quote: continue
        category=next((x for x in top if ticker in (x.get("tickers") or [])),{})
        rrg=rrgmap.get(ticker.upper(),{})
        quadrant=rrg.get("quadrant")
        entry=quote.get("entry_status")
        category_confirm=(safe_num(category.get("rel20")) or 0)>0 and (safe_num(category.get("breadth20")) or 0)>=60
        big_row=big_rows.get(ticker.upper())
        big_state=state_text(big_row) if big_row else "NON PRESENTE"
        big_exit=("EXIT" in big_state or "ESCI" in big_state or "SELL" in big_state)
        big_buy=("BUY" in big_state and not big_exit)
        big_signal=("BUY" if big_buy else "VETO/EXIT" if big_exit else "NON BUY" if big_row else "NON PRESENTE")
        technical_ok=category_confirm and quote["trend_momentum"] and entry=="ZONA INGRESSO"
        operational_label=("BUY POTENZIALE" if technical_ok and big_buy and not big_stale else
                           "ACCUMULO POTENZIALE" if technical_ok and big_row and not big_exit and not big_stale else "WATCHLIST")
        score=(safe_num(category.get("score")) or 0)+(3 if quote["trend_momentum"] else 0)+(2 if quadrant in ("Leading","Improving") else 0)+(1 if entry=="ZONA INGRESSO" else 0)
        results.append({**quote,"group":category.get("group"),"category":category.get("category"),"category_score":category.get("score"),"category_rel20":category.get("rel20"),"category_breadth20":category.get("breadth20"),"category_status":category.get("status"),"rrg_quadrant":quadrant,"rrg_rs_ratio":(rrg.get("trail") or [{}])[-1].get("x"),"rrg_rs_momentum":(rrg.get("trail") or [{}])[-1].get("y"),"category_confirmed":category_confirm,"big_state":big_state,"big_signal":big_signal,"big_match":bool(big_row),"big_fresh":not big_stale,"operational_label":operational_label,"ranking_score":round(score,2),"label":"CANDIDATO" if technical_ok else "WATCHLIST","reason":"Filtro tecnico/categoria verificato; segnale BIG ticker-specific: "+big_signal+(" (feed stale)" if big_stale else "")+". BUY potenziale solo con BIG BUY fresco, conferma categoria, momentum e zona ingresso."})
    results.sort(key=lambda x:(x["label"]!="CANDIDATO",-x["ranking_score"]))
    return results

def state_text(row):
    v=row.get("sta")
    if isinstance(v,list): return " ".join(map(str,v)).upper()
    return str(v or "").upper()
def main():
    now=dt.datetime.now(dt.timezone.utc)
    local=now.astimezone(ZoneInfo("Europe/Rome"))
    data={k:fetch(k,u) for k,u in URLS.items()}
    statuses={}
    for name,obj in data.items():
        statuses[name]={"ok":obj is not None,"source":URLS[name]}
    rot=data["ARRotation"] or {}
    flows=data["Flussi ETFIQ"] or {}
    sel=data["Selezione ARRotation"] or {}
    big=data["BIGCHATGPT"] or {}
    geo=data["GeografiaChatGPT"] or {}
    ucits=data["Geografia UCITS"] or {}
    sniper=data["SniperChatGPT"] or {}
    rrg=data["Sniper RRG"] or {}
    factor_data=data["FactorChatGPT RRG"] or {}
    tax=data["TAX snapshot"] or {}
    tax_history=data["TAX storico"] or {}
    strat=data["TAX strategia"] or {}
    instruments=data["TAX strumenti"] or {}
    watch=data["TAX watchlist"] or {}
    portfolio=data["TAX portafoglio"] or {}

    # Rotazione: non confondere performance di prezzo con flussi monetari.
    cats=rot.get("categories",[]) or []
    cats_sorted=sorted(cats,key=lambda x:safe_num(x.get("score")) if safe_num(x.get("score")) is not None else -1e9,reverse=True)
    top_categories=[]
    for c in cats_sorted[:8]:
        top_categories.append({k:c.get(k) for k in ("group","category","n","ret5","ret20","ret60","rel20","rel60","breadth20","acceleration","score","status","date")})
    sector_theme_categories=[
        {k:c.get(k) for k in ("group","category","n","ret5","ret20","ret60","rel20","rel60","breadth20","acceleration","score","status","date","tickers")}
        for c in cats_sorted if c.get("group") in ("Settori","Temi")
    ][:16]
    positive_cats=[c for c in cats if (safe_num(c.get("ret20")) or 0)>0 and (safe_num(c.get("rel20")) or 0)>0]
    median20=rot.get("benchmark",{}).get("20")
    if median20 is not None and float(median20)<-0.5:
        regime="PRUDENZA SELETTIVA"
        regime_note="La mediana di riferimento a 20 sedute è negativa: privilegiare forza relativa e conferme, senza inseguire i rimbalzi."
    elif len(positive_cats)>=max(1,len(cats)*0.55):
        regime="FAVOREVOLE MA SELETTIVO"
        regime_note="La maggioranza delle categorie mostra forza relativa positiva: cercare ingressi solo con trend confermato."
    else:
        regime="MERCATO MISTO"
        regime_note="La leadership è concentrata: preferire ingressi graduali e mantenere liquidità."
    global_category=next((c for c in cats if c.get("group")=="Geografia" and c.get("category")=="Azionario globale"),None)
    benchmark=fetch_yahoo_benchmark("ACWI.MI")
    if benchmark is None:
        benchmark={"symbol":"Azionario globale · proxy ARRotation","price":None,"price_date":rot.get("latest_bar"),
                   "trailing_1m_pct":None,"trailing_3m_pct":None,"trailing_6m_pct":None,
                   "return_20d_pct":safe_num((global_category or {}).get("ret20")),
                   "relative_20d_pct":safe_num((global_category or {}).get("rel20")),
                   "source":"ARRotation category median; not a tradable benchmark"}
    elif global_category:
        benchmark["return_20d_pct"]=safe_num(global_category.get("ret20"))
        benchmark["relative_20d_pct"]=safe_num(global_category.get("rel20"))
    flow_total=(flows.get("total") or {})
    flow_asof=flows.get("asOf")
    flow_usd=flow_total.get("flowUsd")
    flow_quality="dato disponibile" if flow_usd is not None else "dato non disponibile"

    # Geografia: ranking separati; trend valido solo se prezzo > SMA200 e momentum 12m positivo.
    # Per gli acquisti si usa il registro UCITS verificato, non il radar geografico esplorativo.
    rankings=ucits.get("rankings",{}) or {}
    geo_rows=[]
    for group,arr in rankings.items():
        if not isinstance(arr,list): continue
        for x in arr:
            if not isinstance(x,dict): continue
            eligible=(x.get("status")=="CALCOLATO" and x.get("eligible_trend") is True
                      and x.get("absolute_momentum_positive") is True and x.get("above_sma200") is True)
            if eligible:
                geo_rows.append({**x,"_group":group})
    geo_rows.sort(key=lambda x:safe_num(x.get("composite_momentum")) if safe_num(x.get("composite_momentum")) is not None else -1e9,reverse=True)
    # BIG: stati e segnali restano distinti, niente interpretazioni se il feed non c'è.
    big_rows={str(x.get("t","")).upper():x for x in (big.get("righe",[]) or []) if isinstance(x,dict)}
    # Match tickers nelle categorie di rotazione.
    ticker_category={}
    for c in cats:
        for t in (c.get("tickers",[]) or []): ticker_category[str(t).upper()]=c
    recommendations=[]
    for g in geo_rows:
        symbol=str(g.get("symbol") or g.get("ticker") or "").upper()
        ticker=symbol
        if not ticker: continue
        b=big_rows.get(symbol)
        if b and (b.get("lv") is True or b.get("inv") is True): continue
        cat=ticker_category.get(ticker)
        big_state=state_text(b) if b else "NON DISPONIBILE"
        big_buy="BUY" in big_state and "EXIT" not in big_state and "ESCI" not in big_state
        big_exit=("EXIT" in big_state or "ESCI" in big_state or "SELL" in big_state)
        cat_confirm=bool(cat and (safe_num(cat.get("ret20")) or 0)>0 and (safe_num(cat.get("rel20")) or 0)>0 and (safe_num(cat.get("breadth20")) or 0)>=60)
        price=safe_num(g.get("price")); sma=safe_num(g.get("sma200"))
        gap_pct=((price/sma)-1)*100 if price is not None and sma is not None and sma>0 else None
        zone_low=round(sma*1.02,4) if sma is not None else None
        zone_high=round(sma*1.05,4) if sma is not None else None
        if gap_pct is None: entry_status="LIVELLI NON DISPONIBILI"
        elif gap_pct<=0: entry_status="SOTTO SMA200"
        elif gap_pct<2: entry_status="ATTENDERE CONSOLIDAMENTO"
        elif gap_pct<=5: entry_status="ZONA INGRESSO"
        elif gap_pct<=8: entry_status="ATTENDERE RITRACCIAMENTO"
        else: entry_status="NON INSEGUIRE"
        risk_at_zone_pct=((zone_high-sma)/zone_high)*100 if zone_high and sma else None
        risk_budget_pct=0.5
        position_pct=min(10.0,(risk_budget_pct/risk_at_zone_pct)*100) if risk_at_zone_pct and risk_at_zone_pct>0 else None
        in_entry_zone=entry_status=="ZONA INGRESSO"
        if big_exit: label="ATTESA"
        elif big_buy and cat_confirm and in_entry_zone: label="BUY"
        elif cat_confirm and in_entry_zone: label="ACCUMULO"
        else: label="WATCHLIST"
        reason="Trend geografico confermato (prezzo sopra SMA200 e momentum 12m positivo)"+("; rotazione positiva e ampiezza >=60%" if cat_confirm else "; conferma di rotazione non completa")+("; segnale BIG BUY" if big_buy else "; nessun BUY BIG confermato")+"; "+entry_status.lower()
        recommendations.append({
            "ticker":ticker,"instrument_ticker":g.get("ticker"),"name":g.get("fund") or g.get("name") or g.get("country") or ticker,
            "geography":g.get("country") or g.get("geography") or g.get("module") or g.get("_group"),
            "isin":g.get("isin"),"price":price,"price_date":g.get("price_date") or g.get("latest_price_date"),
            "sma200":sma,"sma200_gap_pct":round(gap_pct,2) if gap_pct is not None else None,
            "entry_zone_low":zone_low,"entry_zone_high":zone_high,"entry_status":entry_status,
            "invalidation_level":round(sma,4) if sma is not None else None,
            "invalidation_rule":"Rivalutare/uscire solo dopo chiusura confermata sotto SMA200; non è uno stop garantito",
            "risk_budget_pct":risk_budget_pct,"max_position_pct":10.0,
            "indicative_position_pct":round(position_pct,1) if position_pct is not None else None,
            "composite_momentum":g.get("composite_momentum"),"momentum_3m":g.get("momentum_3m"),
            "momentum_6m":g.get("momentum_6m"),"momentum_12m":g.get("momentum_12m"),
            "modified_sharpe":g.get("modified_sharpe"),"volatility_annual":g.get("volatility_annual"),
            "above_sma200":g.get("above_sma200"),"absolute_momentum_positive":g.get("absolute_momentum_positive"),
            "big_state":big_state,"rotation_category":cat.get("category") if cat else None,
            "rotation_ret20":cat.get("ret20") if cat else None,"rotation_rel20":cat.get("rel20") if cat else None,
            "rotation_breadth20":cat.get("breadth20") if cat else None,"label":label,"reason":reason
        })
    # Dedup and keep best per ticker; do not rank non-UCITS/factor groups as country funds.
    seen=set(); recs=[]
    for r in recommendations:
        if r["ticker"] not in seen:
            seen.add(r["ticker"]); recs.append(r)
    recs.sort(key=lambda x:({"BUY":0,"ACCUMULO":1,"WATCHLIST":2,"ATTESA":3}.get(x["label"],4),-(safe_num(x.get("composite_momentum")) if safe_num(x.get("composite_momentum")) is not None else -1e9)))
    recs=recs[:12]

    # ARRotation candidate is not an automatic BUY: honor its native state.
    ar_candidates=[]
    for x in (sel.get("candidati",[]) or [])[:10]:
        ar_candidates.append({"ticker":x.get("t"),"name":x.get("nome"),"state":x.get("stato"),"system":x.get("sistema_nome") or x.get("sistema"),"date":x.get("data_segnale"),"confluence":x.get("confluenza"),"price":x.get("prezzo"),"chart":x.get("grafico")})
    # Sniper is strictly paper-only and age-gated.
    sniper_age=age_days(sniper.get("generated_utc"))
    sniper_stale=sniper_age is None or sniper_age>1.5
    rotation_age=age_days(rot.get("generated"))
    geo_age=age_days(ucits.get("generated_at"))
    big_stale=big_age is None or big_age>1.5
    rotation_stale=rotation_age is None or rotation_age>1.5
    geo_stale=geo_age is None or geo_age>1.5
    tax_age=age_days(tax.get("as_of"))
    tax_history_age=age_days(tax_history.get("fetched_at"))
    tax_history_stale=(tax_history_age is None or tax_history_age>2.0
                       or tax_history.get("status")=="unavailable"
                       or not tax_history.get("instruments"))
    tax_series=tax_history.get("instruments",{}) or {}
    tax_position_signals=[]
    for position in (portfolio.get("positions",[]) or []):
        ticker=str(position.get("ticker") or "").upper()
        series=(tax_series.get(ticker) or {}).get("prices",[])
        if not ticker or not series:
            tax_position_signals.append({"ticker":ticker or position.get("raw_name"),"status":"DATI NON DISPONIBILI","signal":"ATTENDERE","reason":"Serie prezzi assente o ticker non identificato"})
            continue
        field="adjclose" if len(series)>0 and series[-1].get("adjclose") else "close"
        values=[safe_num(p.get(field) or p.get("close")) for p in series]
        values=[v for v in values if v is not None and v>0]
        if len(values)<39:
            tax_position_signals.append({"ticker":ticker,"status":"STORICO INSUFFICIENTE","signal":"ATTENDERE","observations":len(values),"last_date":series[-1].get("date")})
            continue
        last=values[-1]
        ma38=sum(values[-38:])/38
        ema=values[0]
        alpha=2/(20+1)
        for value in values[1:]:
            ema=value*alpha+ema*(1-alpha)
        roc38=(last/values[-39]-1)*100
        ao=(sum(values[-5:])/5)-(sum(values[-34:])/34) if len(values)>=34 else None
        ma200=sum(values[-200:])/200 if len(values)>=200 else None
        trend=bool(ma200 is not None and last>ma200)
        momentum=roc38>0
        if ma200 is None:
            signal="ATTENDERE"; status="STORICO < 200 SEDUTE"
        elif trend and momentum and ao is not None and ao>0:
            signal="MANTENERE / MONITORARE"; status="TREND POSITIVO"
        elif not trend and not momentum:
            signal="RIDURRE RISCHIO / VERIFICARE"; status="DEBOLEZZA CONFERMATA"
        else:
            signal="ATTENDERE CONFERMA"; status="SEGNALE MISTO"
        cost=safe_num(position.get("average_cost"))
        last_close=safe_num(series[-1].get("close"))
        tax_position_signals.append({
            "ticker":ticker,"name":position.get("raw_name"),"last_price":last_close,
            "last_date":series[-1].get("date"),"average_cost":cost,
            "return_vs_cost_pct":round((last_close/cost-1)*100,2) if last_close and cost else None,
            "ma38":round(ma38,4),"ma200":round(ma200,4) if ma200 else None,
            "roc38_pct":round(roc38,2),"ema20":round(ema,4),"ao_close_proxy":round(ao,4) if ao is not None else None,
            "above_ma200":trend,"signal":signal,"status":status
        })
    tax_history_last=tax_history.get("latest_date")
    tax_covered=len(tax_series)
    tax_factor_assets=[]
    for asset in (factor_data.get("assets",[]) or []):
        trail=asset.get("trail",[]) or []
        if not trail: continue
        point=trail[-1]
        tax_factor_assets.append({
            "ticker":asset.get("ticker"),"label":asset.get("label"),
            "factor":str(asset.get("label") or "").split("·")[0].strip(),
            "quadrant":asset.get("quadrant"),"date":point.get("date"),
            "rs_ratio":point.get("x"),"rs_momentum":point.get("y")
        })
    factor_age=age_days(factor_data.get("updated"))
    factor_stale=factor_age is None or factor_age>3
    big_age=age_days(big.get("gen"))
    big_stale=big_age is None or big_age>1.5
    big_age=age_days(big.get("gen"))
    big_stale=big_age is None or big_age>1.5
    big_candidate_rows={str(x.get("t","")).upper():x for x in (big.get("righe",[]) or []) if isinstance(x,dict)}
    sector_theme_candidates=build_sector_theme_candidates(cats_sorted,factor_data,big_candidate_rows,big_stale)
    quadrant_order={"Leading":0,"Improving":1,"Weakening":2,"Lagging":3}
    tax_factor_assets.sort(key=lambda x:(quadrant_order.get(x.get("quadrant"),4),x.get("factor") or "",x.get("ticker") or ""))
    # Recommendation gate: if a required feed is missing/stale, downgrade any BUY.
    blockers=[]
    if not statuses["BIGCHATGPT"]["ok"]: blockers.append("Feed BIG non disponibile: BUY quantitativi sospesi.")
    if not statuses["FactorChatGPT RRG"]["ok"]: blockers.append("Feed FactorChatGPT RRG non disponibile: fattori esclusi dal ranking.")
    if not statuses["GeografiaChatGPT"]["ok"]: blockers.append("Feed geografico non disponibile: ranking geografici sospesi.")
    if not statuses["ARRotation"]["ok"]: blockers.append("Feed ARRotation non disponibile: conferme di rotazione sospese.")
    if tax_history_stale: blockers.append("TAX: storico prezzi mancante/obsoleto; segnali sul portafoglio sospesi.")
    if factor_stale: blockers.append("FactorChatGPT: RRG fattoriale non aggiornato; rotazione fattori esclusa.")
    if sniper_stale: blockers.append("Sniper: segnali non aggiornati; esclusi dalle decisioni operative.")
    if big_stale: blockers.append("BIG: feed tecnico non aggiornato; BUY quantitativi sospesi.")
    if rotation_stale: blockers.append("ARRotation: feed non aggiornato; conferme di rotazione sospese.")
    if geo_stale: blockers.append("Geografia UCITS: ranking non aggiornato; segnali geografici sospesi.")
    if not statuses["BIGCHATGPT"]["ok"] or not statuses["GeografiaChatGPT"]["ok"] or not statuses["ARRotation"]["ok"] or big_stale or rotation_stale or geo_stale:
        for r in recs:
            if r["label"]=="BUY": r["label"]="WATCHLIST"
            elif r["label"]=="ACCUMULO" and (rotation_stale or geo_stale): r["label"]="WATCHLIST"
    buy_count=sum(1 for x in recs if x["label"]=="BUY")
    accum_count=sum(1 for x in recs if x["label"]=="ACCUMULO")
    report={
      "schema_version":1,"generated_utc":now.isoformat(),"generated_local":local.isoformat(),
      "edition":"11:00" if local.hour==11 else ("23:00" if local.hour==23 else "STRAORDINARIA"),
      "market":{"regime":regime,"note":regime_note,"benchmark_return_20":median20,"category_count":len(cats),"positive_relative_categories":len(positive_cats),"top_categories":top_categories},
      "benchmark":benchmark,
      "flows":{"as_of":flow_asof,"flow_usd":flow_usd,"flow_pct_assets":flow_total.get("flowPctOfStartNetAssets"),"inflows_usd":flow_total.get("inflowsUsd"),"outflows_usd":flow_total.get("outflowsUsd"),"funds_in":flow_total.get("fundsIn"),"funds_out":flow_total.get("fundsOut"),"quality":flow_quality},
      "geography":{"generated_at":ucits.get("generated_at"),"age_days":geo_age,"stale":geo_stale,"latest_price_date":ucits.get("latest_price_date"),"trend_candidates":len(geo_rows),"top":recs},
      "rotation":{"generated":rot.get("generated"),"age_days":rotation_age,"stale":rotation_stale,"latest_bar":rot.get("latest_bar"),"universe":rot.get("universe"),"eligible":rot.get("eligible"),"loaded":rot.get("tickers_loaded"),"candidate_count":(sel.get("riepilogo") or {}).get("candidati"),"exit_count":(sel.get("riepilogo") or {}).get("uscite"),"open_signals":(sel.get("riepilogo") or {}).get("segnalazioni_aperte"),"candidates":ar_candidates,"top_categories":top_categories},
      "big":{"generated":big.get("gen"),"age_days":big_age,"stale":big_stale,"rows":len(big.get("righe",[]) or []),"systems":len(big.get("sistemi",[]) or []),"buy_count":buy_count,"accumulate_count":accum_count},
      "sniper":{"generated":sniper.get("generated_utc"),"paper_only":bool(sniper.get("paper_only",True)),"signal_count":sniper.get("signal_count",len(sniper.get("signals",[]) or [])),"age_days":sniper_age,"rrg_generated":rrg.get("generated_utc"),"rrg_instruments":rrg.get("instruments"),"rrg_fetch_ok":(rrg.get("fetch_status") or {}).get("ok"),"rrg_fetch_total":(rrg.get("fetch_status") or {}).get("total")},
      "sector_themes":{"as_of":rot.get("latest_bar"),"categories":sector_theme_categories,"candidates":sector_theme_candidates,"candidate_count":len(sector_theme_candidates),"verified_quotes":len(sector_theme_candidates),"sector_count":sum(1 for x in sector_theme_categories if x.get("group")=="Settori"),"theme_count":sum(1 for x in sector_theme_categories if x.get("group")=="Temi"),"method":"Rotazione relativa categoria; prezzi ticker da Yahoo daily, candidati non BUY."},
      "factors":{"updated":factor_data.get("updated"),"age_days":factor_age,"stale":factor_stale,"benchmark":factor_data.get("benchmark"),"frequency":factor_data.get("frequency"),"method":factor_data.get("method"),"assets":tax_factor_assets,"quadrants":{q:sum(1 for x in tax_factor_assets if x.get("quadrant")==q) for q in ("Leading","Improving","Weakening","Lagging")}},
      "tax":{"as_of":tax.get("as_of"),"snapshot_stale":tax_age is None or tax_age>3,"history_fetched_at":tax_history.get("fetched_at"),"history_age_days":tax_history_age,"history_latest_date":tax_history_last,"history_status":tax_history.get("status"),"history_stale":tax_history_stale,"history_instruments":tax_covered,"history_unresolved":len(tax_history.get("unresolved",[]) or []),"instrument_count":len(instruments.get("instruments",[]) or []),"watchlist_count":len(watch.get("tickers",[]) or []),"portfolio_positions":len(portfolio.get("positions",[]) or []),"position_signals":tax_position_signals,"strategy":strat.get("model_name"),"roc":(strat.get("parameters") or {}).get("roc_period"),"ma_fast":(strat.get("parameters") or {}).get("moving_average_fast"),"ma_slow":(strat.get("parameters") or {}).get("moving_average_slow")},
      "recommendations":recs,"buy_count":buy_count,"accumulate_count":accum_count,"blockers":blockers,
      "sources":statuses,
      "disclaimer":"Bollettino quantitativo informativo. BUY richiede conferma simultanea BIG + trend geografico + rotazione positiva; ACCUMULO richiede trend geografico e rotazione positiva. Nessun ordine automatico. I segnali Sniper paper-only sono esclusi."
    }
    # Declassifica recommendations se feed BIG è presente ma il ticker non ha un BUY nativo.
    # ACCUMULO resta esplicitamente graduale, non un acquisto immediato.
    out=DATA/"bollettino.json"
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    hist_path=DATA/"bollettino_storico.json"
    try: hist=json.loads(hist_path.read_text(encoding="utf-8"))
    except Exception: hist={"editions":[]}
    editions=hist.get("editions",[])
    unique=[]; seen_editions=set()
    for item in editions:
        key=(str(item.get("generated_local") or item.get("generated_utc") or "")[:10],item.get("edition"))
        if key in seen_editions: continue
        seen_editions.add(key); unique.append(item)
    editions=unique
    # Aggiorna il rendimento osservato delle raccomandazioni passate usando lo stesso feed UCITS
    # (prezzi rettificati Yahoo, proxy e non NAV ufficiale).
    current_prices={}
    for arr in (ucits.get("rankings",{}) or {}).values():
        if not isinstance(arr,list): continue
        for item in arr:
            if not isinstance(item,dict): continue
            symbol=str(item.get("symbol") or item.get("ticker") or "").upper()
            price=safe_num(item.get("price"))
            if symbol and price is not None:
                current_prices[symbol]={"price":price,"date":item.get("price_date") or ucits.get("latest_price_date")}
    for edition in editions:
        ed_date=parse_date(edition.get("generated_utc"))
        age=(now-ed_date).total_seconds()/86400 if ed_date else None
        for rec in edition.get("recommendations",[]):
            current=current_prices.get(str(rec.get("ticker","")).upper())
            base=safe_num(rec.get("price"))
            if not current or base is None or base<=0: continue
            latest=current["price"]
            rec["latest_price"]=latest
            rec["latest_price_date"]=current["date"]
            rec["return_since_entry_pct"]=round((latest/base-1)*100,2)
            old_bench_price=safe_num((edition.get("benchmark") or {}).get("price"))
            current_bench_price=safe_num(benchmark.get("price"))
            if old_bench_price and current_bench_price:
                bench_return=round((current_bench_price/old_bench_price-1)*100,2)
                rec["benchmark_return_since_entry_pct"]=bench_return
                rec["excess_return_vs_benchmark_pct"]=round(rec["return_since_entry_pct"]-bench_return,2)
            if age is not None and age>=30 and "return_1m_pct" not in rec: rec["return_1m_pct"]=rec["return_since_entry_pct"]
            if age is not None and age>=90 and "return_3m_pct" not in rec: rec["return_3m_pct"]=rec["return_since_entry_pct"]
            if age is not None and age>=180 and "return_6m_pct" not in rec: rec["return_6m_pct"]=rec["return_since_entry_pct"]
        old_bench=edition.get("benchmark") or {}
        # I rendimenti trailing alla data di ingresso non sono checkpoint futuri.
        for key in ("return_1m_pct","return_3m_pct","return_6m_pct"):
            old_bench.pop(key,None)
        old_bench_base=safe_num(old_bench.get("price"))
        new_bench_price=safe_num(benchmark.get("price"))
        if old_bench_base and new_bench_price:
            old_bench["latest_price"]=new_bench_price
            old_bench["latest_price_date"]=benchmark.get("price_date")
            old_bench["return_since_entry_pct"]=round((new_bench_price/old_bench_base-1)*100,2)
            if age is not None and age>=30 and "return_1m_pct" not in old_bench: old_bench["return_1m_pct"]=old_bench["return_since_entry_pct"]
            if age is not None and age>=90 and "return_3m_pct" not in old_bench: old_bench["return_3m_pct"]=old_bench["return_since_entry_pct"]
            if age is not None and age>=180 and "return_6m_pct" not in old_bench: old_bench["return_6m_pct"]=old_bench["return_since_entry_pct"]
            edition["benchmark"]=old_bench
    if os.getenv("ARCHIVE_EDITION","1")!="0":
        edition_key=(local.date().isoformat(),report["edition"])
        existing=[i for i,e in enumerate(editions) if (str(e.get("generated_local") or e.get("generated_utc") or "")[:10],e.get("edition"))==edition_key]
        new_edition={"generated_utc":report["generated_utc"],"generated_local":report["generated_local"],"edition":report["edition"],"regime":regime,"benchmark":benchmark,"recommendations":[{"ticker":x["ticker"],"label":x["label"],"price":x.get("price"),"price_date":x.get("price_date"),"reason":x["reason"]} for x in recs],"buy_count":buy_count,"accumulate_count":accum_count}
        if existing: editions[existing[0]]=new_edition
        else: editions.append(new_edition)
    hist={"schema_version":1,"description":"Archivio delle edizioni e rendimenti dei consigli rispetto al benchmark globale ACWI.MI; prezzi rettificati Yahoo Finance, proxy e non NAV ufficiale.","editions":editions[-365:]}
    hist_path.write_text(json.dumps(hist,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"generated":report["generated_local"],"sources_ok":sum(1 for x in statuses.values() if x["ok"]),"sources_total":len(statuses),"regime":regime,"buy":buy_count,"accumulate":accum_count,"blockers":blockers},ensure_ascii=False))
if __name__=="__main__": main()
