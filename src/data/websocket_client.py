"""Live WebSocket Client — real ccxt.pro + high-fidelity simulator fallback"""
from __future__ import annotations
import asyncio, time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Deque, Dict, List, Optional
import numpy as np, pandas as pd
from src.utils.logger import get_logger
logger = get_logger(__name__)

try:
    import ccxt.pro as ccxtpro; CCXT_PRO = True
except ImportError:
    ccxtpro = None; CCXT_PRO = False

@dataclass
class LiveCandle:
    symbol:str; timeframe:str; timestamp:object
    open:float; high:float; low:float; close:float; volume:float
    is_closed:bool=False

@dataclass
class OrderBookSnapshot:
    symbol:str; timestamp:object; bids:List; asks:List; spread_pct:float=0.0
    @property
    def mid_price(self):
        return (self.bids[0][0]+self.asks[0][0])/2 if self.bids and self.asks else 0.
    @property
    def bid_ask_imbalance(self):
        bv=sum(b[1] for b in self.bids[:5]); av=sum(a[1] for a in self.asks[:5])
        return (bv-av)/max(bv+av,1e-10)

class LiveMarketSimulator:
    BASE={"BTC/USDT":67000,"ETH/USDT":3200,"SOL/USDT":145,"BNB/USDT":420}
    VOLS={"BTC/USDT":.0035,"ETH/USDT":.0040,"SOL/USDT":.0055,"BNB/USDT":.0038}
    SPBPS={"BTC/USDT":1.,"ETH/USDT":1.2,"SOL/USDT":2.,"BNB/USDT":1.5}

    def __init__(self, symbols:List[str], seed:int=2024):
        self._rng=np.random.default_rng(seed); self._symbols=symbols
        self._prices={s:self.BASE.get(s,1000.)*self._rng.uniform(.92,1.08) for s in symbols}
        self._regimes={s:"trend" for s in symbols}
        self._rtimer={s:0 for s in symbols}
        self._drifts={s:self._rng.uniform(5e-5,2e-4) for s in symbols}

    def next_tick(self, sym:str)->float:
        self._rtimer[sym]+=1
        if self._rtimer[sym]>self._rng.integers(80,200):
            self._regimes[sym]=self._rng.choice(["trend","range","volatile"],p=[.55,.30,.15])
            self._rtimer[sym]=0
            self._drifts[sym]=(self._rng.choice([-1,1])*self._rng.uniform(1e-4,3e-4)
                               if self._regimes[sym]=="trend" else self._rng.uniform(-3e-5,3e-5))
        vsc={"trend":1.,"range":1.3,"volatile":3.5}[self._regimes[sym]]
        vol=self.VOLS.get(sym,.003)*vsc; cm=0.
        if sym!="BTC/USDT" and "BTC/USDT" in self._prices:
            cm=(self._prices["BTC/USDT"]/self.BASE.get("BTC/USDT",1)-1)*\
               {"ETH/USDT":.82,"SOL/USDT":.75,"BNB/USDT":.70}.get(sym,0)*.05
        ret=self._drifts[sym]+cm+self._rng.normal(0,vol)
        if self._rng.random()<.001: ret+=self._rng.choice([-1,1])*self._rng.uniform(.003,.008)
        self._prices[sym]*=(1+ret); return float(self._prices[sym])

    def get_orderbook(self, sym:str)->OrderBookSnapshot:
        p=self._prices.get(sym,self.BASE.get(sym,1000)); sp=self.SPBPS.get(sym,2.)/10000
        bids=[[p*(1-sp*(i+1)*.5),abs(self._rng.normal(1,.4))] for i in range(10)]
        asks=[[p*(1+sp*(i+1)*.5),abs(self._rng.normal(1,.4))] for i in range(10)]
        return OrderBookSnapshot(sym,datetime.now(timezone.utc),bids,asks,sp*100)

    def generate_history(self, sym:str, bars:int=600)->pd.DataFrame:
        saved=self._prices.get(sym,self.BASE.get(sym,1000))
        self._prices[sym]=self.BASE.get(sym,1000)*self._rng.uniform(.88,1.12)
        rows=[]
        for i in range(bars,-1,-1):
            p=self.next_tick(sym); v=self.VOLS.get(sym,.003)
            o=p*(1+self._rng.normal(0,v*.3)); h=max(o,p)*(1+abs(self._rng.normal(0,v)))
            lo=min(o,p)*(1-abs(self._rng.normal(0,v))); vol=abs(self._rng.normal(500,200))
            rows.append({"open":o,"high":h,"low":lo,"close":p,"volume":vol})
        self._prices[sym]=saved
        dates=pd.date_range(end=pd.Timestamp.now(tz="UTC"),periods=len(rows),freq="1h")
        df=pd.DataFrame(rows,index=dates)
        df["high"]=df[["high","open","close"]].max(axis=1)
        df["low"]=df[["low","open","close"]].min(axis=1)
        return df

class LiveDataFeed:
    def __init__(self, symbols:List[str], exchange_name:str="bitget"):
        self._symbols=symbols; self._exname=exchange_name
        self._sim=LiveMarketSimulator(symbols); self._use_real=CCXT_PRO
        self._exchange=None; self._running=False
        self._cbs:Dict[str,List[Callable]]=defaultdict(list)
        self._history:Dict[str,Deque[LiveCandle]]={s:deque(maxlen=600) for s in symbols}
        self._obs:Dict[str,Optional[OrderBookSnapshot]]={s:None for s in symbols}
        self._ticks=0; self._t0=None
        mode="REAL_WS" if self._use_real else "SIMULATOR"
        logger.info(f"LiveDataFeed: mode={mode} exchange={exchange_name} symbols={symbols}")

    async def start(self):
        self._running=True; self._t0=time.monotonic()
        if self._use_real: asyncio.create_task(self._real_ws_task())
        else:
            logger.info("Network offline → high-fidelity simulator active")
            asyncio.create_task(self._sim_loop())

    async def stop(self):
        self._running=False
        if self._exchange:
            try: await self._exchange.close()
            except: pass

    def subscribe_candles(self, sym:str, cb:Callable): self._cbs[f"c:{sym}"].append(cb)

    def get_history_df(self, sym:str, bars:int=500)->pd.DataFrame:
        if len(self._history[sym])>=60:
            rows=[{"open":c.open,"high":c.high,"low":c.low,"close":c.close,"volume":c.volume}
                  for c in self._history[sym]]
            dates=[c.timestamp for c in self._history[sym]]
            df=pd.DataFrame(rows,index=dates)
            df["high"]=df[["high","open","close"]].max(axis=1)
            df["low"]=df[["low","open","close"]].min(axis=1)
            return df
        return self._sim.generate_history(sym,bars=bars)

    def get_latest_price(self, sym:str)->float:
        return self._history[sym][-1].close if self._history[sym] \
               else self._sim._prices.get(sym,self._sim.BASE.get(sym,1000))

    def get_spread_pct(self, sym:str)->float:
        ob=self._obs.get(sym) or self._sim.get_orderbook(sym); return ob.spread_pct

    @property
    def tick_count(self)->int: return self._ticks
    @property
    def uptime_hours(self)->float: return (time.monotonic()-self._t0)/3600 if self._t0 else 0.

    async def _real_ws_task(self):
        try:
            cls=getattr(ccxtpro,self._exname,None)
            if not cls: raise ImportError(f"ccxt.pro: {self._exname} not found")
            self._exchange=cls({"enableRateLimit":True})
            await asyncio.gather(*[asyncio.create_task(self._ws_candle(s)) for s in self._symbols],
                                  return_exceptions=True)
        except Exception as e:
            logger.warning(f"Real WS failed ({e}), using simulator")
            self._use_real=False; asyncio.create_task(self._sim_loop())

    async def _ws_candle(self, sym:str):
        while self._running:
            try:
                for ts,o,h,l,c,v in await self._exchange.watch_ohlcv(sym,"1m"):
                    can=LiveCandle(sym,"1m",pd.Timestamp(ts,unit="ms",tz="UTC"),o,h,l,c,v,True)
                    self._history[sym].append(can); self._ticks+=1
                    for cb in self._cbs.get(f"c:{sym}",[]):
                        if asyncio.iscoroutinefunction(cb): asyncio.create_task(cb(can))
                        else: cb(can)
            except Exception as e: logger.debug(f"WS {sym}: {e}"); await asyncio.sleep(5)

    async def _sim_loop(self):
        partials={s:{"o":None,"h":-1e18,"l":1e18,"v":0.,"t":0} for s in self._symbols}
        while self._running:
            for sym in self._symbols:
                p=self._sim.next_tick(sym); par=partials[sym]
                if par["o"] is None: par["o"]=p
                par["h"]=max(par["h"],p); par["l"]=min(par["l"],p)
                par["v"]+=abs(float(self._sim._rng.normal(200,80))); par["t"]+=1
                if par["t"]>=60:
                    c=LiveCandle(sym,"1h",pd.Timestamp.now(tz="UTC"),
                                 par["o"],par["h"],par["l"],p,par["v"],True)
                    self._history[sym].append(c); self._ticks+=1
                    self._obs[sym]=self._sim.get_orderbook(sym)
                    for cb in self._cbs.get(f"c:{sym}",[]):
                        if asyncio.iscoroutinefunction(cb): asyncio.create_task(cb(c))
                        else: cb(c)
                    partials[sym]={"o":None,"h":-1e18,"l":1e18,"v":0.,"t":0}
            await asyncio.sleep(0.05)
