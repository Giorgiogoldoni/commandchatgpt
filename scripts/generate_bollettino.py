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
 "TAX snapshot": "https://raw.githubusercontent.com/Giorgiogoldoni/TAX-ETP-MANAGER/main/data/market_snapshot.json",
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
    try:
        return dt.datetime.fromisoformat(str(s).replace(" UTC","+00:00").replace("Z","+00:00")).replace(tzinfo=dt.timezone.utc) if "T" not in str(s) else dt.datetime.fromisoformat(str(s).replace("Z","+00:00")).astimezone(dt.timezone.utc)
    except Exception:
        try: return dt.datetime.strptime(str(s),"%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        except Exception: return None
def age_days(s):
    d=parse_date(s)
    return (dt.datetime.now(dt.timezone.utc)-d).total_seconds()/86400 if d else None
def safe_num(v):
    try: return float(v) if v is not None else None
    except Exception: return None
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
    tax=data["TAX snapshot"] or {}
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
        if big_exit: label="ATTESA"
        elif big_buy and cat_confirm: label="BUY"
        elif cat_confirm: label="ACCUMULO"
        else: label="WATCHLIST"
        # Evita di trasformare segnali isolati in raccomandazioni: le tre condizioni sono esplicite.
        recommendations.append({
            "ticker":ticker,"instrument_ticker":g.get("ticker"),"name":g.get("name") or g.get("fund") or g.get("geography") or ticker,
            "geography":g.get("geography") or g.get("country") or g.get("module") or g.get("_group"),
            "isin":g.get("isin"),"price":g.get("price"),"price_date":g.get("price_date") or g.get("latest_price_date"),
            "composite_momentum":g.get("composite_momentum"),"momentum_12m":g.get("momentum_12m"),
            "above_sma200":g.get("above_sma200"),"absolute_momentum_positive":g.get("absolute_momentum_positive"),
            "big_state":big_state,"rotation_category":cat.get("category") if cat else None,
            "rotation_ret20":cat.get("ret20") if cat else None,"rotation_rel20":cat.get("rel20") if cat else None,
            "rotation_breadth20":cat.get("breadth20") if cat else None,"label":label,
            "reason":"Trend geografico confermato (prezzo sopra SMA200 e momentum 12m positivo)"+("; rotazione positiva e ampiezza >=60%" if cat_confirm else "; conferma di rotazione non completa")+("; segnale BIG BUY" if big_buy else "; nessun BUY BIG confermato")
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
    big_age=age_days(big.get("gen"))
    rotation_age=age_days(rot.get("generated"))
    geo_age=age_days(ucits.get("generated_at"))
    big_stale=big_age is None or big_age>1.5
    rotation_stale=rotation_age is None or rotation_age>1.5
    geo_stale=geo_age is None or geo_age>1.5
    tax_age=age_days(tax.get("as_of"))
    tax_stale=tax_age is None or tax_age>3
    # Recommendation gate: if a required feed is missing/stale, downgrade any BUY.
    blockers=[]
    if not statuses["BIGCHATGPT"]["ok"]: blockers.append("Feed BIG non disponibile: BUY quantitativi sospesi.")
    if not statuses["GeografiaChatGPT"]["ok"]: blockers.append("Feed geografico non disponibile: ranking geografici sospesi.")
    if not statuses["ARRotation"]["ok"]: blockers.append("Feed ARRotation non disponibile: conferme di rotazione sospese.")
    if tax_stale: blockers.append("TAX: snapshot prezzi obsoleto; nessuna decisione sul portafoglio.")
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
      "flows":{"as_of":flow_asof,"flow_usd":flow_usd,"flow_pct_assets":flow_total.get("flowPctOfStartNetAssets"),"inflows_usd":flow_total.get("inflowsUsd"),"outflows_usd":flow_total.get("outflowsUsd"),"funds_in":flow_total.get("fundsIn"),"funds_out":flow_total.get("fundsOut"),"quality":flow_quality},
      "geography":{"generated_at":ucits.get("generated_at"),"age_days":geo_age,"stale":geo_stale,"latest_price_date":ucits.get("latest_price_date"),"trend_candidates":len(geo_rows),"top":recs},
      "rotation":{"generated":rot.get("generated"),"age_days":rotation_age,"stale":rotation_stale,"latest_bar":rot.get("latest_bar"),"universe":rot.get("universe"),"eligible":rot.get("eligible"),"loaded":rot.get("tickers_loaded"),"candidate_count":(sel.get("riepilogo") or {}).get("candidati"),"exit_count":(sel.get("riepilogo") or {}).get("uscite"),"open_signals":(sel.get("riepilogo") or {}).get("segnalazioni_aperte"),"candidates":ar_candidates,"top_categories":top_categories},
      "big":{"generated":big.get("gen"),"age_days":big_age,"stale":big_stale,"rows":len(big.get("righe",[]) or []),"systems":len(big.get("sistemi",[]) or []),"buy_count":buy_count,"accumulate_count":accum_count},
      "sniper":{"generated":sniper.get("generated_utc"),"paper_only":bool(sniper.get("paper_only",True)),"signal_count":sniper.get("signal_count",len(sniper.get("signals",[]) or [])),"age_days":sniper_age,"rrg_generated":rrg.get("generated_utc"),"rrg_instruments":rrg.get("instruments"),"rrg_fetch_ok":(rrg.get("fetch_status") or {}).get("ok"),"rrg_fetch_total":(rrg.get("fetch_status") or {}).get("total")},
      "tax":{"as_of":tax.get("as_of"),"status":tax.get("status"),"stale":tax_stale,"age_days":tax_age,"instrument_count":len(instruments.get("instruments",[]) or []),"watchlist_count":len(watch.get("tickers",[]) or []),"portfolio_positions":len(portfolio.get("positions",[]) or []),"strategy":strat.get("model_name"),"roc":(strat.get("parameters") or {}).get("roc_period"),"ma_fast":(strat.get("parameters") or {}).get("moving_average_fast"),"ma_slow":(strat.get("parameters") or {}).get("moving_average_slow")},
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
    editions.append({"generated_utc":report["generated_utc"],"generated_local":report["generated_local"],"edition":report["edition"],"regime":regime,"recommendations":[{"ticker":x["ticker"],"label":x["label"],"price":x.get("price"),"price_date":x.get("price_date"),"reason":x["reason"]} for x in recs],"buy_count":buy_count,"accumulate_count":accum_count})
    hist={"schema_version":1,"description":"Archivio delle edizioni; prezzi di riferimento e decisioni salvati al momento della pubblicazione.","editions":editions[-365:]}
    hist_path.write_text(json.dumps(hist,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"generated":report["generated_local"],"sources_ok":sum(1 for x in statuses.values() if x["ok"]),"sources_total":len(statuses),"regime":regime,"buy":buy_count,"accumulate":accum_count,"blockers":blockers},ensure_ascii=False))
if __name__=="__main__": main()
