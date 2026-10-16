
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

try:
    import pandas as pd
except Exception as exc:
    pd = None
    PANDAS_IMPORT_ERROR = exc

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

APP_TITLE = "KSISU Data Intelligence Workbench"
APP_SUBTITLE = "Source → Registry → Raw → Quality → Harmonisation → Curated Data → Intelligence"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INCOMING_DIR = DATA_DIR / "incoming"
DEMO_DIR = INCOMING_DIR / "demo_district_artifacts"
TEMPLATE_DIR = BASE_DIR / "data_templates"
RUNTIME_DIR = BASE_DIR / "runtime"
RAW_STORE_DIR = RUNTIME_DIR / "raw_store"
CURATED_DIR = RUNTIME_DIR / "curated"
EXPORT_DIR = RUNTIME_DIR / "exports"
AUDIT_DIR = RUNTIME_DIR / "audit"
DB_PATH = RUNTIME_DIR / "ksisu.db"

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".html", ".htm"}

CANONICAL_FIELDS = [
    "record_id", "source", "year", "date", "institution", "district", "state",
    "sector", "industry_name", "nic_code", "occupation", "nco_code", "skill",
    "training_capacity", "completions", "employment", "demand", "supply",
    "wage", "migrants", "notes"
]

COLUMN_ALIASES = {
    "id":"record_id", "recordid":"record_id", "record_id":"record_id",
    "source":"source", "source_name":"source", "publisher":"source",
    "year":"year", "fy":"year", "financial_year":"year", "fin_year":"year", "fiscal_year":"year", "period":"year",
    "date":"date", "updated":"date", "update_date":"date",
    "college":"institution", "institution":"institution", "institute":"institution",
    "organisation":"institution", "organization":"institution", "company":"institution",
    "district":"district", "district_name":"district", "districtname":"district", "location":"district",
    "state":"state", "state_name":"state",
    "sector":"sector", "sector_name":"sector",
    "industry":"industry_name", "industry_name":"industry_name", "industryname":"industry_name",
    "nic":"nic_code", "nic_code":"nic_code", "niccode":"nic_code", "industry_code":"nic_code",
    "occupation":"occupation", "job_role":"occupation", "jobrole":"occupation",
    "job_role_name":"occupation", "designation":"occupation", "role":"occupation", "trade":"occupation",
    "nco":"nco_code", "nco_code":"nco_code", "ncocode":"nco_code", "occupation_code":"nco_code",
    "skill":"skill", "skill_name":"skill", "course":"skill", "course_name":"skill",
    "training_capacity":"training_capacity", "capacity":"training_capacity", "seats":"training_capacity",
    "completions":"completions", "completed":"completions", "graduates":"completions",
    "employment":"employment", "employed":"employment", "placements":"employment",
    "demand":"demand", "job_demand":"demand", "jobs":"demand", "vacancies":"demand",
    "required_workers":"demand", "required_workers_count":"demand",
    "supply":"supply", "skilled_supply":"supply", "workers":"supply", "labour_supply":"supply",
    "wage":"wage", "salary":"wage", "avg_wage":"wage",
    "migrants":"migrants", "migration":"migrants", "migrant_count":"migrants",
    "notes":"notes", "remarks":"notes", "comment":"notes"
}

DISTRICT_ALIASES = {
    "bangalore":"Bengaluru Urban", "bangalore urban":"Bengaluru Urban",
    "bengaluru":"Bengaluru Urban", "bengaluru urban":"Bengaluru Urban",
    "mysore":"Mysuru", "mysuru":"Mysuru",
    "belgaum":"Belagavi", "belagavi":"Belagavi",
    "gulbarga":"Kalaburagi", "kalaburagi":"Kalaburagi",
    "shimoga":"Shivamogga", "shivamogga":"Shivamogga",
    "tumkur":"Tumakuru", "tumakuru":"Tumakuru",
    "chikmagalur":"Chikkamagaluru", "chikkamagaluru":"Chikkamagaluru",
    "bellary":"Ballari", "ballari":"Ballari",
    "bijapur":"Vijayapura", "vijayapura":"Vijayapura",
}

NUMERIC_FIELDS = {"year","training_capacity","completions","employment","demand","supply","wage","migrants"}

DISTRICTS = [
    "Bagalkot","Ballari","Belagavi","Bengaluru Rural","Bengaluru Urban","Bidar",
    "Chamarajanagar","Chikkaballapur","Chikkamagaluru","Chitradurga","Dakshina Kannada",
    "Davanagere","Dharwad","Gadag","Hassan","Haveri","Kalaburagi","Kodagu","Kolar","Koppal",
    "Mandya","Mysuru","Raichur","Ramanagara","Shivamogga","Tumakuru","Udupi",
    "Uttara Kannada","Vijayanagara","Vijayapura","Yadgir"
]

def ensure_dirs():
    for d in [RUNTIME_DIR, RAW_STORE_DIR, CURATED_DIR, EXPORT_DIR, AUDIT_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def clean_text(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    value = str(value).replace("\u00a0"," ")
    return re.sub(r"\s+"," ",value).strip()

def norm_key(value):
    value = clean_text(value).lower()
    value = re.sub(r"[\u2010-\u2015]","-",value)
    value = re.sub(r"[^a-z0-9]+"," ",value)
    return re.sub(r"\s+"," ",value).strip()

def safe_num(value):
    if value is None:
        return None
    text = clean_text(value).replace(",","")
    text = re.sub(r"[%₹$]","",text).strip()
    if not text:
        return None
    try:
        f = float(text)
        return int(f) if f.is_integer() else f
    except Exception:
        return None

def parse_year(value):
    text = clean_text(value)
    if not text:
        return None
    m = re.search(r"(19\d{2}|20\d{2})", text)
    return int(m.group(1)) if m else safe_num(text)

def sha256(path):
    h = hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def detect_delimiter(path):
    with open(path,"r",encoding="utf-8-sig",newline="") as f:
        sample = f.read(8000)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|\t").delimiter
    except Exception:
        return ","

def read_table(path):
    if pd is None:
        raise RuntimeError(f"pandas is required: {PANDAS_IMPORT_ERROR}")
    path = Path(path)
    s = path.suffix.lower()
    if s in {".xlsx",".xls"}:
        return pd.read_excel(path)
    if s == ".json":
        try:
            return pd.read_json(path)
        except Exception:
            return pd.json_normalize(json.loads(path.read_text(encoding="utf-8")))
    if s in {".html",".htm"}:
        tables = pd.read_html(path)
        return tables[0] if tables else pd.DataFrame()
    if s == ".csv":
        return pd.read_csv(path, sep=detect_delimiter(path), encoding="utf-8-sig", low_memory=False)
    raise ValueError(f"Unsupported connector for {path.name}")

def standardize_columns(columns):
    result = {}
    used = set()
    for col in columns:
        raw = clean_text(col)
        key = norm_key(raw).replace(" ","_")
        target = COLUMN_ALIASES.get(key, key if key in CANONICAL_FIELDS else "")
        if target and target not in used:
            result[raw] = target
            used.add(target)
        else:
            result[raw] = ""
    return result

def apply_canonical_columns(df, overrides=None):
    overrides = overrides or {}
    lineage_fields = {"_source_file_id","_source_file","_source_path","_ingested_at"}
    mapping = standardize_columns(df.columns)
    for col in df.columns:
        if col in lineage_fields:
            mapping[col] = col
        else:
            key = (str(col).strip(), norm_key(col))
            if key in overrides:
                mapping[col] = overrides[key]
    rename = {src: dst for src,dst in mapping.items() if dst}
    out = df.rename(columns=rename).copy()
    existing = set(out.columns)
    for original,target in mapping.items():
        if target:
            continue
        if original in out.columns:
            base = "raw_" + re.sub(r"[^a-z0-9]+","_",norm_key(original)).strip("_")
            base = base or "raw_field"
            candidate = base
            i = 2
            while candidate in existing:
                candidate = f"{base}_{i}"
            out[candidate] = out[original]
            existing.add(candidate)
            out.drop(columns=[original],inplace=True,errors="ignore")
    for field in CANONICAL_FIELDS:
        if field not in out.columns:
            out[field] = ""
    return out

def clean_dataframe(df):
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(clean_text)
    for col in NUMERIC_FIELDS:
        if col in out.columns:
            out[col] = out[col].map(parse_year if col=="year" else safe_num)
    if "date" in out.columns:
        parsed = pd.to_datetime(out["date"],errors="coerce",dayfirst=True)
        out["date"] = parsed.dt.strftime("%Y-%m-%d").fillna("")
    placeholders = {"na","n/a","nan","none","null","-","--","not available","not applicable"}
    for col in out.columns:
        out[col] = out[col].map(lambda x: "" if norm_key(x) in placeholders else x)
    return out

def exact_duplicate_mask(df):
    derived = {
        "_source_file_id","_source_file","_ingested_at","district_standard","lgd_code",
        "district_map_status","district_map_confidence","district_map_method",
        "industry_standard","nic_standard_code","industry_map_status",
        "industry_map_confidence","industry_map_method","occupation_standard",
        "nco_standard_code","occupation_map_status","occupation_map_confidence",
        "occupation_map_method","district_id","district_key","industry_key",
        "occupation_key","analysis_supply","analysis_supply_method","analysis_demand"
    }
    compare_cols = [c for c in df.columns if c not in derived]
    if not compare_cols:
        return pd.Series([False]*len(df), index=df.index)
    x = df[compare_cols].fillna("").astype(str)
    x = x.apply(lambda s: s.str.lower().str.strip())
    return x.duplicated(keep="first")

def record_key(row):
    parts = []
    for field in ("record_id","institution","occupation","skill","industry_name","district","year"):
        value = clean_text(row.get(field,""))
        if value:
            parts.append(norm_key(value))
    return "|".join(parts)

def near_duplicate_groups(df, threshold=0.93, max_rows=5000):
    if len(df) > max_rows:
        return []
    rows = df.to_dict("records")
    buckets = defaultdict(list)
    for i,row in enumerate(rows):
        key = record_key(row)
        buckets[key[:16] if key else f"row{i%100}"].append(i)
    groups = []
    seen = set()
    for idxs in buckets.values():
        if len(idxs)<2:
            continue
        for p,i in enumerate(idxs):
            if i in seen:
                continue
            a = record_key(rows[i])
            if len(a)<6:
                continue
            group=[i]
            for j in idxs[p+1:]:
                if j in seen:
                    continue
                b=record_key(rows[j])
                score=SequenceMatcher(None,a,b).ratio()
                if score>=threshold:
                    group.append(j)
                    seen.add(j)
            if len(group)>1:
                seen.add(i)
                groups.append({"indexes":group,"score":min(SequenceMatcher(None,a,record_key(rows[j])).ratio() for j in group[1:])})
    return groups

class Registry:
    def __init__(self, db_path):
        ensure_dirs()
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init()

    def _init(self):
        c=self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS source_files(
            file_id TEXT PRIMARY KEY,
            source_path TEXT,
            raw_store_path TEXT,
            source_name TEXT,
            dataset_name TEXT,
            district_hint TEXT,
            period_start TEXT,
            period_end TEXT,
            format TEXT,
            record_count INTEGER,
            schema_json TEXT,
            checksum TEXT,
            version INTEGER,
            update_frequency TEXT,
            privacy_level TEXT,
            department TEXT,
            access_method TEXT,
            source_url TEXT,
            last_updated TEXT,
            next_expected_update TEXT,
            status TEXT,
            ingested_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS schema_maps(
            file_id TEXT,
            source_column TEXT,
            canonical_field TEXT,
            confidence REAL,
            method TEXT,
            PRIMARY KEY(file_id, source_column)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS processing_runs(
            run_id TEXT PRIMARY KEY,
            started_at TEXT,
            finished_at TEXT,
            files_processed INTEGER,
            rows_processed INTEGER,
            status TEXT,
            notes TEXT
        )""")
        self.conn.commit()

    def register(self,path,frame):
        path=Path(path); now=datetime.now().isoformat(timespec="seconds")
        checksum=sha256(path)
        cur=self.conn.cursor()
        cur.execute("SELECT version FROM source_files WHERE checksum=?",(checksum,))
        existing=cur.fetchone()
        if existing:
            return None, checksum, existing[0]
        cur.execute("SELECT COALESCE(MAX(version),0) FROM source_files WHERE source_name=? AND dataset_name=?",(path.name,path.stem))
        version=int(cur.fetchone()[0])+1
        # district hint: exact district filename or known alias
        district_hint=""
        nk=norm_key(path.stem)
        for d in DISTRICTS:
            if norm_key(d)==nk or norm_key(d) in nk or nk in norm_key(d):
                district_hint=d; break
        if not district_hint and nk in DISTRICT_ALIASES:
            district_hint=DISTRICT_ALIASES[nk]
        years=[]
        if "year" in frame.columns:
            years=[int(v) for v in frame["year"].map(parse_year).dropna().tolist() if isinstance(v,(int,float))]
        period_start=str(min(years)) if years else ""
        period_end=str(max(years)) if years else ""
        file_id=f"FILE-{checksum[:10].upper()}"
        raw_name=f"{file_id}_{path.name}"
        raw_path=RAW_STORE_DIR/raw_name
        shutil.copy2(path,raw_path)
        privacy="Public / synthetic demo" if "demo" in str(path).lower() or "data_status" in frame.columns else "Unclassified"
        suffix=path.suffix.lower().lstrip(".")
        access_method={"xlsx":"Excel upload","xls":"Excel upload","csv":"CSV upload","json":"JSON connector","html":"HTML connector","htm":"HTML connector"}.get(suffix,"File connector")
        source_url=""
        if "source_url" in frame.columns:
            vals=[clean_text(x) for x in frame["source_url"].tolist() if clean_text(x)]
            source_url=vals[0] if vals else ""
        department="Demo source" if "demo" in str(path).lower() else "Unclassified"
        meta=(file_id,str(path),str(raw_path),path.name,path.stem,district_hint,period_start,period_end,
              suffix,len(frame),json.dumps([str(c) for c in frame.columns]),checksum,version,
              "Manual / demo",privacy,department,access_method,source_url,"","","Ingested",now)
        cur.execute("""INSERT INTO source_files VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",meta)
        self.conn.commit()
        # schema mapping
        mapping=standardize_columns(frame.columns)
        for src,target in mapping.items():
            conf=1.0 if target else 0.0
            method="alias_dictionary" if target else "unmapped"
            cur.execute("INSERT OR REPLACE INTO schema_maps VALUES(?,?,?,?,?)",(file_id,src,target,conf,method))
        self.conn.commit()
        return file_id,checksum,version

    def rows(self):
        q="SELECT * FROM source_files ORDER BY ingested_at DESC"
        return self.conn.execute(q).fetchall()

    def schema_rows(self):
        return self.conn.execute("SELECT * FROM schema_maps ORDER BY file_id, source_column").fetchall()

    def export_csv(self,path):
        rows=self.rows()
        cols=[d[1] for d in self.conn.execute("PRAGMA table_info(source_files)").fetchall()]
        pd.DataFrame(rows,columns=cols).to_csv(path,index=False,encoding="utf-8-sig")

class MappingEngine:
    def __init__(self):
        self.masters={"district":{},"industry":{},"occupation":{}}
        self.sources={"district":"Built-in aliases","industry":"Not loaded","occupation":"Not loaded"}

    def import_master(self,kind,path):
        df=read_table(path)
        cols={norm_key(c).replace(" ","_"):c for c in df.columns}
        src_col=cols.get("source_value") or cols.get("alias") or cols.get("source") or cols.get("name")
        name_col=cols.get("standard_name") or cols.get("name") or cols.get(kind)
        code_col=cols.get("standard_code") or cols.get("code") or cols.get("lgd_code") or cols.get("nic_code") or cols.get("nco_code")
        if not src_col or not name_col:
            raise ValueError("Mapping file needs source_value/alias/name and standard_name/name columns.")
        m={}
        for _,r in df.iterrows():
            src=clean_text(r.get(src_col,"")); name=clean_text(r.get(name_col,""))
            code=clean_text(r.get(code_col,"")) if code_col else ""
            if src and name:
                m[norm_key(src)]={"name":name,"code":code,"method":"master"}
        self.masters[kind]=m
        self.sources[kind]=str(path)
        return len(m)

    def map_value(self,kind,value):
        text=clean_text(value); key=norm_key(text)
        if not key:
            return {"name":"","code":"","status":"blank","confidence":0.0,"method":"none"}
        if key in self.masters.get(kind,{}):
            item=self.masters[kind][key]
            return {**item,"status":"mapped","confidence":1.0}
        if kind=="district" and key in DISTRICT_ALIASES:
            return {"name":DISTRICT_ALIASES[key],"code":"","status":"mapped","confidence":0.98,"method":"built-in alias"}
        if kind=="industry" and re.fullmatch(r"\d{2,5}",text):
            return {"name":"","code":text,"status":"code_only","confidence":0.90,"method":"source code"}
        if kind=="occupation" and re.fullmatch(r"\d{4,6}",text):
            return {"name":"","code":text,"status":"code_only","confidence":0.90,"method":"source code"}
        return {"name":text,"code":"","status":"review","confidence":0.0,"method":"unmapped"}

class WorkbenchEngine:
    def __init__(self):
        ensure_dirs()
        self.registry=Registry(DB_PATH)
        self.mapping_engine=MappingEngine()
        self.raw_frames=[]
        self.raw_paths=[]
        self.schema_overrides={}
        self.df=pd.DataFrame()
        self.quality_files=pd.DataFrame()
        self.quality={}
        self.near_dupes=[]
        self.last_intelligence=pd.DataFrame()
        self.last_recommendations=[]
        self.last_ksi_note="Official KSI formula is not asserted by this prototype. The app surfaces the analytical inputs and gaps that could feed the eventual KSI."

    def discover(self,root=INCOMING_DIR,extra_paths=None):
        found=[]
        root=Path(root)
        if root.exists():
            found += [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        for p in extra_paths or []:
            pp=Path(p)
            if pp.exists() and pp.is_file() and pp.suffix.lower() in SUPPORTED_EXTENSIONS:
                found.append(pp)
        seen={}
        for p in found:
            try:
                seen[str(p.resolve())]=p
            except Exception:
                seen[str(p)]=p
        return sorted(seen.values(),key=lambda x:str(x).lower())

    def load_schema_overrides(self,path):
        df=read_table(path)
        required={"source_file","source_column","canonical_field"}
        if not required.issubset({str(c) for c in df.columns}):
            raise ValueError("Schema override file needs source_file, source_column, canonical_field columns.")
        count=0
        for _,r in df.iterrows():
            sf=clean_text(r.get("source_file",""))
            sc=clean_text(r.get("source_column",""))
            cf=clean_text(r.get("canonical_field",""))
            if sf and sc and cf in CANONICAL_FIELDS:
                self.schema_overrides[(sf, norm_key(sc))]=cf
                count+=1
        return count

    def ingest(self,paths):
        frames=[]
        accepted=[]
        registry_rows=[]
        for path in paths:
            frame=read_table(path)
            if frame is None or frame.empty:
                continue
            frame["_source_path"]=str(path)
            file_id,checksum,version=self.registry.register(path,frame)
            if file_id is None:
                # Existing artifact: find id by checksum
                row=self.registry.conn.execute("SELECT file_id FROM source_files WHERE checksum=?",(checksum,)).fetchone()
                file_id=row[0] if row else f"FILE-{checksum[:10].upper()}"
            frame["_source_file_id"]=file_id
            frame["_source_file"]=Path(path).name
            frame["_ingested_at"]=datetime.now().isoformat(timespec="seconds")
            # Apply source-specific schema overrides before common harmonisation.
            ov={(k, norm_key(k)):v for (sf,k),v in self.schema_overrides.items() if sf==Path(path).name}
            frame=apply_canonical_columns(frame, ov)
            frames.append(frame)
            accepted.append(path)
        if not frames:
            return 0,0
        combined=pd.concat(frames,ignore_index=True,sort=False)
        combined=apply_canonical_columns(combined)
        # restore lineage fields if canonicalisation moved around
        for col in ["_source_file_id","_source_file","_source_path","_ingested_at"]:
            if col not in combined.columns:
                combined[col]=""
        combined=clean_dataframe(combined)
        self.raw_frames=frames
        self.raw_paths=accepted
        self.df=combined
        self.run_quality()
        return len(accepted),len(combined)

    def run_quality(self):
        if self.df is None or self.df.empty:
            self.quality={}; self.quality_files=pd.DataFrame(); self.near_dupes=[]; return
        df=self.df
        self.near_dupes=near_duplicate_groups(df)
        exact=int(exact_duplicate_mask(df).sum())
        rows=len(df)
        metrics={
            "Rows":rows,
            "Columns":len(df.columns),
            "Exact duplicates":exact,
            "Near duplicate groups":len(self.near_dupes),
            "Missing district":int((df["district"].fillna("").astype(str).str.strip()=="").sum()),
            "Missing occupation":int((df["occupation"].fillna("").astype(str).str.strip()=="").sum()),
            "Missing industry":int((df["industry_name"].fillna("").astype(str).str.strip()=="").sum()),
            "Missing demand":int((df["demand"].isna() | (df["demand"].astype(str)=="")).sum()),
            "Missing supply":int((df["supply"].isna() | (df["supply"].astype(str)=="")).sum())
        }
        completeness=1 - (metrics["Missing district"]+metrics["Missing occupation"]+metrics["Missing industry"])/(max(1,rows*3))
        uniqueness=1 - exact/max(1,rows)
        validity=1 - (metrics["Missing demand"]+metrics["Missing supply"])/(max(1,rows*2))
        self.quality=metrics
        # Per-file catalog quality
        file_rows=[]
        for fid,g in df.groupby("_source_file_id",dropna=False):
            file_rows.append({
                "file_id":clean_text(fid),
                "rows":len(g),
                "missing_district":int((g["district"].fillna("").astype(str).str.strip()=="").sum()),
                "missing_occupation":int((g["occupation"].fillna("").astype(str).str.strip()=="").sum()),
                "missing_industry":int((g["industry_name"].fillna("").astype(str).str.strip()=="").sum()),
                "missing_demand":int((g["demand"].isna() | (g["demand"].astype(str)=="")).sum()),
                "missing_supply":int((g["supply"].isna() | (g["supply"].astype(str)=="")).sum()),
                "quality_score":round(100*(0.30*completeness+0.30*uniqueness+0.20*validity+0.20),2)
            })
        self.quality_files=pd.DataFrame(file_rows)

    def deduplicate(self,near=False):
        if self.df.empty:
            return 0
        mask=exact_duplicate_mask(self.df)
        removed=int(mask.sum())
        self.df=self.df.loc[~mask].reset_index(drop=True)
        if near and self.near_dupes:
            drop=set()
            for grp in self.near_dupes:
                drop.update(grp["indexes"][1:])
            drop=[i for i in drop if i<len(self.df)]
            self.df=self.df.drop(index=drop).reset_index(drop=True)
            removed += len(drop)
        self.run_quality()
        return removed

    def harmonise(self):
        if self.df.empty:
            return
        d=self.df["district"].map(lambda x:self.mapping_engine.map_value("district",x))
        self.df["district_standard"]=d.map(lambda x:x["name"])
        self.df["lgd_code"]=d.map(lambda x:x["code"])
        self.df["district_map_status"]=d.map(lambda x:x["status"])
        self.df["district_map_confidence"]=d.map(lambda x:x["confidence"])
        self.df["district_map_method"]=d.map(lambda x:x["method"])
        self.df["district_id"]=self.df["lgd_code"].where(self.df["lgd_code"].astype(str).str.strip()!="",self.df["district_standard"].map(lambda x:"DISTRICT-"+norm_key(x).replace(" ","-").upper() if clean_text(x) else ""))
        ind_input=self.df["industry_name"].where(self.df["industry_name"].astype(str).str.strip()!="",self.df["nic_code"])
        i=ind_input.map(lambda x:self.mapping_engine.map_value("industry",x))
        self.df["industry_standard"]=i.map(lambda x:x["name"])
        self.df["nic_standard_code"]=i.map(lambda x:x["code"])
        self.df["industry_map_status"]=i.map(lambda x:x["status"])
        self.df["industry_map_confidence"]=i.map(lambda x:x["confidence"])
        self.df["industry_map_method"]=i.map(lambda x:x["method"])
        oinput=self.df["occupation"].where(self.df["occupation"].astype(str).str.strip()!="",self.df["nco_code"])
        o=oinput.map(lambda x:self.mapping_engine.map_value("occupation",x))
        self.df["occupation_standard"]=o.map(lambda x:x["name"])
        self.df["nco_standard_code"]=o.map(lambda x:x["code"])
        self.df["occupation_map_status"]=o.map(lambda x:x["status"])
        self.df["occupation_map_confidence"]=o.map(lambda x:x["confidence"])
        self.df["occupation_map_method"]=o.map(lambda x:x["method"])

    def build_curated(self):
        if self.df.empty:
            return {}
        self.harmonise()
        d=self.df.copy()
        d["occupation_code"]=d["nco_standard_code"].where(d["nco_standard_code"].astype(str).str.strip()!="",d["nco_code"])
        d["industry_code"]=d["nic_standard_code"].where(d["nic_standard_code"].astype(str).str.strip()!="",d["nic_code"])
        # Training supply
        training_cols=["district_id","institution","skill","occupation_code","year","training_capacity","completions","employment"]
        training=d[training_cols].copy()
        training["institution_id"]=training["institution"].map(lambda x:"INST-"+hashlib.sha1(norm_key(x).encode()).hexdigest()[:8] if clean_text(x) else "")
        training=training.rename(columns={"institution":"institution_name","skill":"course_code","employment":"placed"})
        # Demand
        demand_cols=["district_id","industry_code","occupation_code","year","demand","wage"]
        demand=d[demand_cols].copy()
        demand=demand.rename(columns={"demand":"vacancies"})
        # Economic activity
        econ=d[["district_id","industry_code","year","institution","employment","wage"]].copy()
        econ["enterprise_count"]=econ["institution"].map(lambda x:1 if clean_text(x) else 0)
        econ=econ.rename(columns={"institution":"entity_name"})
        # labour supply
        lab=d[["district_id","occupation_code","year","employment","supply","completions"]].copy()
        lab["formal_employment"]=lab["employment"]
        lab["labour_force"]=lab["supply"]
        lab["unemployed"]=""
        lab["employed"]=lab["employment"]
        self._write_curated("training_supply",training)
        self._write_curated("skill_demand",demand)
        self._write_curated("economic_activity",econ)
        self._write_curated("labour_supply",lab)
        # Also master curated fact table
        curated_fact=d[[
            "_source_file_id","district_id","district_standard","industry_standard","nic_standard_code",
            "occupation_standard","nco_standard_code","year","sector","demand","supply","completions",
            "training_capacity","employment","wage","migrants"
        ]].copy()
        self._write_curated("curated_fact",curated_fact)
        return {"training_supply":len(training),"skill_demand":len(demand),"economic_activity":len(econ),"labour_supply":len(lab),"curated_fact":len(curated_fact)}

    def _write_curated(self,name,df):
        path=CURATED_DIR/f"{name}.csv"
        df.to_csv(path,index=False,encoding="utf-8-sig")
        with sqlite3.connect(DB_PATH) as conn:
            safe_name=re.sub(r"[^a-zA-Z0-9_]","_",name)
            conn.execute(f'DROP TABLE IF EXISTS "{safe_name}"')
            df.to_sql(safe_name,conn,index=False,if_exists="replace")
        return path

    def compute_intelligence(self):
        if self.df.empty:
            self.last_intelligence=pd.DataFrame(); self.last_recommendations=[]; return self.last_intelligence
        self.harmonise()
        df=self.df.copy()
        df["district_key"]=df["district_standard"].where(df["district_standard"].astype(str).str.strip()!="",df["district"])
        df["industry_key"]=df["industry_standard"].where(df["industry_standard"].astype(str).str.strip()!="",df["industry_name"])
        df["occupation_key"]=df["occupation_standard"].where(df["occupation_standard"].astype(str).str.strip()!="",df["occupation"])
        demand=pd.to_numeric(df["demand"],errors="coerce")
        direct_supply=pd.to_numeric(df["supply"],errors="coerce")
        method=pd.Series(["direct_supply" if pd.notna(v) else "" for v in direct_supply],index=df.index)
        supply=direct_supply.copy()
        completion=pd.to_numeric(df["completions"],errors="coerce")
        training_capacity=pd.to_numeric(df["training_capacity"],errors="coerce")
        supply=supply.where(supply.notna(),completion)
        method=method.mask(method=="", "completions")
        supply=supply.where(supply.notna(),training_capacity)
        method=method.mask(method=="", "training_capacity")
        method=method.mask(supply.isna(),"unavailable")
        df["analysis_supply"]=supply
        df["analysis_supply_method"]=method
        df["analysis_demand"]=demand
        groups=[]
        for keys,g in df.groupby(["district_key","industry_key","occupation_key"],dropna=False):
            district,industry,occupation=[clean_text(v) for v in keys]
            dem=g["analysis_demand"].sum(min_count=1)
            sup=g["analysis_supply"].sum(min_count=1)
            gap=float(dem-sup) if pd.notna(dem) and pd.notna(sup) else None
            gap_pct=(gap/dem*100.0) if gap is not None and dem else None
            completeness=sum(bool(clean_text(g[f].iloc[0])) for f in ["district_key","industry_key","occupation_key"])
            if pd.notna(dem): completeness+=1
            if pd.notna(sup): completeness+=1
            mapping_conf=float(pd.concat([
                pd.to_numeric(g["district_map_confidence"],errors="coerce"),
                pd.to_numeric(g["industry_map_confidence"],errors="coerce"),
                pd.to_numeric(g["occupation_map_confidence"],errors="coerce")
            ]).mean()) if len(g) else 0
            confidence="High" if completeness>=5 and mapping_conf>=0.8 and len(g)>=2 else ("Medium" if completeness>=4 else "Low")
            signal="DATA INSUFFICIENT"
            if gap is not None:
                if gap<=0: signal="SUPPLY ≥ DEMAND"
                elif gap_pct is not None and gap_pct>=30: signal="HIGH SKILL GAP"
                else: signal="POTENTIAL SKILL GAP"
            source_ids=";".join(sorted({clean_text(x) for x in g["_source_file_id"].tolist() if clean_text(x)}))
            years=",".join(sorted({str(int(v)) for v in pd.to_numeric(g["year"],errors="coerce").dropna().tolist()}))
            groups.append({
                "district":district,"industry":industry,"occupation":occupation,"records":len(g),
                "supply":round(float(sup),2) if pd.notna(sup) else None,
                "supply_method":"mixed" if len(set(g["analysis_supply_method"]))>1 else clean_text(g["analysis_supply_method"].iloc[0]),
                "demand":round(float(dem),2) if pd.notna(dem) else None,
                "gap":round(gap,2) if gap is not None else None,
                "gap_pct":round(gap_pct,2) if gap_pct is not None else None,
                "confidence":confidence,"mapping_confidence":round(mapping_conf,2),
                "years":years,"source_file_ids":source_ids
            })
        result=pd.DataFrame(groups)
        if not result.empty:
            result["signal"]=result.apply(self._signal,axis=1)
            result["recommendation"]=result.apply(self._recommendation,axis=1)
        self.last_intelligence=result
        self.last_recommendations=result[["district","industry","occupation","signal","confidence","recommendation"]].to_dict("records") if not result.empty else []
        return result

    @staticmethod
    def _signal(r):
        if pd.isna(r.get("gap")): return "DATA INSUFFICIENT"
        if float(r["gap"])<=0: return "SUPPLY ≥ DEMAND"
        if pd.notna(r.get("gap_pct")) and float(r["gap_pct"])>=30: return "HIGH SKILL GAP"
        return "POTENTIAL SKILL GAP"

    @staticmethod
    def _recommendation(r):
        district=r.get("district") or "district"; occupation=r.get("occupation") or "occupation"; industry=r.get("industry") or "sector"
        sig=r.get("signal")
        if sig=="HIGH SKILL GAP":
            return f"Consider increasing relevant training capacity and employer-linked apprenticeship opportunities for {occupation} in {district}, subject to validation."
        if sig=="POTENTIAL SKILL GAP":
            return f"Review course mix and industry linkage for {occupation} in {district}; validate demand indicators before reallocating resources."
        if sig=="SUPPLY ≥ DEMAND":
            return f"Monitor {industry} in {district} and assess whether training capacity should be rebalanced toward higher-demand occupations."
        return f"Collect additional demand and supply evidence for {district} / {occupation} before policy action."

    def export_schema_map(self,path):
        rows=self.registry.schema_rows()
        pd.DataFrame(rows,columns=["file_id","source_column","canonical_field","confidence","method"]).to_csv(path,index=False,encoding="utf-8-sig")

    def export_mapping_review(self,path):
        if self.df.empty:
            pd.DataFrame().to_csv(path,index=False)
            return
        rows=[]
        for kind,src,std,code,status,conf,method in [
            ("district","district","district_standard","lgd_code","district_map_status","district_map_confidence","district_map_method"),
            ("industry","industry_name","industry_standard","nic_standard_code","industry_map_status","industry_map_confidence","industry_map_method"),
            ("occupation","occupation","occupation_standard","nco_standard_code","occupation_map_status","occupation_map_confidence","occupation_map_method")
        ]:
            sub=self.df[[src,std,code,status,conf,method]].drop_duplicates()
            for _,r in sub.iterrows():
                if clean_text(r[src]) and clean_text(r[status]) in {"review","code_only"}:
                    rows.append({"mapping_type":kind,"source_value":clean_text(r[src]),
                                  "suggested_standard_value":clean_text(r[std]),
                                  "suggested_code":clean_text(r[code]),"status":clean_text(r[status]),
                                  "confidence":r[conf],"method":clean_text(r[method])})
        pd.DataFrame(rows).to_csv(path,index=False,encoding="utf-8-sig")

    def export_intelligence(self,path):
        if self.last_intelligence.empty:
            self.compute_intelligence()
        self.last_intelligence.to_csv(path,index=False,encoding="utf-8-sig")

    def export_cleaned(self,path):
        self.df.to_csv(path,index=False,encoding="utf-8-sig")

    def audit_log(self,action,notes=""):
        ensure_dirs()
        p=AUDIT_DIR/"processing_log.jsonl"
        with p.open("a",encoding="utf-8") as f:
            f.write(json.dumps({"time":datetime.now().isoformat(timespec="seconds"),"action":action,"notes":notes},ensure_ascii=False)+"\n")

class Style:
    BG="#F4F7FB"; SURFACE="#FFFFFF"; NAVY="#10213B"; BLUE="#1D63D7"; MUTED="#64748B"; BORDER="#D9E2EE"; GREEN="#0F766E"; RED="#B42318"; AMBER="#A16207"; TEXT="#1F2937"
    @classmethod
    def apply(cls,root):
        root.configure(bg=cls.BG)
        s=ttk.Style(root); s.theme_use("clam")
        s.configure(".",font=("Segoe UI",9),background=cls.BG,foreground=cls.TEXT)
        s.configure("TFrame",background=cls.BG); s.configure("TLabel",background=cls.BG,foreground=cls.TEXT)
        s.configure("Header.TLabel",background=cls.NAVY,foreground="white",font=("Segoe UI",16,"bold"))
        s.configure("SubHeader.TLabel",background=cls.NAVY,foreground="#C9D6EA",font=("Segoe UI",9))
        s.configure("Section.TLabel",background=cls.BG,foreground=cls.NAVY,font=("Segoe UI",12,"bold"))
        s.configure("Primary.TButton",background=cls.BLUE,foreground="white",padding=(10,7),font=("Segoe UI",9,"bold"))
        s.map("Primary.TButton",background=[("active","#174EAB")])
        s.configure("Treeview",rowheight=25,background=cls.SURFACE,fieldbackground=cls.SURFACE,foreground=cls.TEXT)
        s.configure("Treeview.Heading",background="#E8EFF8",foreground=cls.NAVY,font=("Segoe UI",9,"bold"))
        s.configure("Notebook",background=cls.BG,borderwidth=0); s.configure("TNotebook.Tab",padding=(11,7),font=("Segoe UI",9,"bold"))
        s.configure("TProgressbar",troughcolor="#E5EBF3",background=cls.BLUE)

class App:
    def __init__(self):
        if pd is None:
            raise RuntimeError(f"pandas/openpyxl is required: {PANDAS_IMPORT_ERROR}")
        ensure_dirs()
        self.root=tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1500x930")
        self.root.minsize(1180,760)
        Style.apply(self.root)
        self.engine=WorkbenchEngine()
        self.discovered=[]
        self.status=tk.StringVar(value="Ready — use Discover Sources or Ingest All Demo Sources.")
        self._build_header()
        self._build_toolbar()
        self._build_kpis()
        self._build_notebook()
        self.refresh_all()

    def _build_header(self):
        h=tk.Frame(self.root,bg=Style.NAVY,height=78); h.pack(fill=tk.X); h.pack_propagate(False)
        left=tk.Frame(h,bg=Style.NAVY); left.pack(side=tk.LEFT,padx=18,pady=10)
        ttk.Label(left,text=APP_TITLE,style="Header.TLabel").pack(anchor="w")
        ttk.Label(left,text=APP_SUBTITLE,style="SubHeader.TLabel").pack(anchor="w")
        tk.Label(h,text="31-DISTRICT DEMO = SOURCE ARTIFACTS  •  PRODUCTION = SOURCE-DRIVEN",bg=Style.NAVY,fg="#93C5FD",font=("Segoe UI",8,"bold")).pack(side=tk.RIGHT,padx=18)

    def _build_toolbar(self):
        f=ttk.Frame(self.root,padding=(12,9)); f.pack(fill=tk.X)
        ttk.Button(f,text="Discover Sources",style="Primary.TButton",command=self.discover_sources).pack(side=tk.LEFT,padx=3)
        ttk.Button(f,text="Load Schema Overrides",command=self.load_schema_overrides).pack(side=tk.LEFT,padx=3)
        ttk.Button(f,text="Load Demo Masters",command=self.load_demo_masters).pack(side=tk.LEFT,padx=3)
        ttk.Button(f,text="Ingest All Discovered",command=self.ingest_all).pack(side=tk.LEFT,padx=3)
        ttk.Button(f,text="Run Quality",command=self.run_quality).pack(side=tk.LEFT,padx=3)
        ttk.Button(f,text="Harmonise",command=self.harmonise).pack(side=tk.LEFT,padx=3)
        ttk.Button(f,text="Build Curated Layer",command=self.build_curated).pack(side=tk.LEFT,padx=3)
        ttk.Button(f,text="Run Skill Gap",style="Primary.TButton",command=self.compute_intelligence).pack(side=tk.LEFT,padx=3)
        ttk.Button(f,text="Export Bundle",command=self.export_bundle).pack(side=tk.LEFT,padx=3)
        ttk.Button(f,text="Open Runtime",command=lambda:webbrowser.open(RUNTIME_DIR.as_uri())).pack(side=tk.LEFT,padx=3)
        ttk.Label(f,textvariable=self.status,foreground=Style.MUTED).pack(side=tk.RIGHT,padx=6)
        pipeline=ttk.Frame(self.root,padding=(12,0,12,8)); pipeline.pack(fill=tk.X)
        self.pipeline_var=tk.StringVar(value="SOURCE DISCOVERY  →  REGISTRY  →  RAW  →  QUALITY  →  LGD/NCO/NIC  →  CURATED  →  SKILL GAP")
        ttk.Label(pipeline,textvariable=self.pipeline_var,foreground=Style.BLUE,font=("Segoe UI",9,"bold")).pack(anchor="w")

    def _build_kpis(self):
        bar=tk.Frame(self.root,bg=Style.BG); bar.pack(fill=tk.X,padx=12,pady=(0,8))
        self.kpis={}
        items=[("sources","Sources"),("ingested","Files Ingested"),("rows","Records"),("quality","Quality Score"),("mapped","Mapped Rows"),("alerts","Gap Alerts")]
        for key,label in items:
            card=tk.Frame(bar,bg=Style.SURFACE,highlightbackground=Style.BORDER,highlightthickness=1)
            card.pack(side=tk.LEFT,fill=tk.BOTH,expand=True,padx=3)
            var=tk.StringVar(value="0"); self.kpis[key]=var
            tk.Label(card,textvariable=var,bg=Style.SURFACE,fg=Style.NAVY,font=("Segoe UI",17,"bold")).pack(pady=(7,0))
            tk.Label(card,text=label,bg=Style.SURFACE,fg=Style.MUTED,font=("Segoe UI",8)).pack(pady=(0,7))

    def _build_notebook(self):
        nb=ttk.Notebook(self.root); nb.pack(fill=tk.BOTH,expand=True,padx=12,pady=4); self.nb=nb
        self.tabs=[]
        for title, builder in [
            ("1. Source Registry",self._tab_registry),
            ("2. Data Quality",self._tab_quality),
            ("3. Schema Mapper",self._tab_schema),
            ("4. Harmonisation",self._tab_mapping),
            ("5. Curated Layer",self._tab_curated),
            ("6. Intelligence",self._tab_intel),
            ("7. Lineage",self._tab_lineage),
            ("Reference",self._tab_reference),
        ]:
            tab=ttk.Frame(nb,padding=8); nb.add(tab,text=f" {title} "); self.tabs.append(tab); builder(tab)

    def tree(self,parent,cols,head,widths):
        wrap=ttk.Frame(parent); wrap.pack(fill=tk.BOTH,expand=True)
        t=ttk.Treeview(wrap,columns=cols,show="headings")
        for c,h,w in zip(cols,head,widths): t.heading(c,text=h); t.column(c,width=w,anchor=tk.W)
        y=ttk.Scrollbar(wrap,orient=tk.VERTICAL,command=t.yview); x=ttk.Scrollbar(wrap,orient=tk.HORIZONTAL,command=t.xview)
        t.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        t.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns"); x.grid(row=1,column=0,sticky="ew")
        wrap.rowconfigure(0,weight=1); wrap.columnconfigure(0,weight=1)
        return t

    def _tab_registry(self,tab):
        top=ttk.Frame(tab); top.pack(fill=tk.X)
        ttk.Label(top,text="Data Catalog / Source Registry",style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Label(top,text="Every artifact gets a file_id, checksum, version, schema, period, district hint and status.",foreground=Style.MUTED).pack(side=tk.LEFT,padx=10)
        ttk.Button(top,text="Export Source Registry",command=self.export_registry).pack(side=tk.RIGHT)
        self.registry_tree=self.tree(tab,
            ("file_id","source_name","dataset","district","format","rows","checksum","version","privacy","status"),
            ["File ID","Source Artifact","Dataset","District Hint","Format","Rows","Checksum","Version","Privacy","Status"],
            [125,190,160,135,70,70,100,70,150,95])
        self.registry_tree.bind("<<TreeviewSelect>>",lambda e:self.show_selected_source())

    def _tab_quality(self,tab):
        top=ttk.Frame(tab); top.pack(fill=tk.X)
        ttk.Label(top,text="Data Quality Engine",style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(top,text="Drop Exact Duplicates",command=self.drop_exact).pack(side=tk.RIGHT,padx=3)
        ttk.Button(top,text="Near-Dupe Review",command=self.show_near).pack(side=tk.RIGHT,padx=3)
        self.quality_tree=self.tree(tab,("metric","value","meaning"),["Metric","Value","Interpretation"],[260,120,800])
        self.quality_text=ScrolledText(tab,height=8,font=("Consolas",9),bg="white",relief="flat"); self.quality_text.pack(fill=tk.X,pady=(8,0))

    def _tab_schema(self,tab):
        top=ttk.Frame(tab); top.pack(fill=tk.X)
        ttk.Label(top,text="Schema Detection / Data Mapper",style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(top,text="Export Schema Mapping",command=self.export_schema).pack(side=tk.RIGHT)
        ttk.Label(tab,text="Detects equivalent fields. Optional source-specific overrides are loaded from data_templates/schema_override_TEMPLATE.csv.",foreground=Style.MUTED).pack(anchor="w",pady=5)
        self.schema_tree=self.tree(tab,("file_id","source_column","canonical","confidence","method"),["File ID","Source Column","Canonical Field","Confidence","Method"],[130,260,220,100,180])

    def _tab_mapping(self,tab):
        top=ttk.Frame(tab); top.pack(fill=tk.X)
        ttk.Label(top,text="LGD / NCO / NIC Harmonisation",style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(top,text="Import LGD Master",command=lambda:self.load_master("district")).pack(side=tk.RIGHT,padx=3)
        ttk.Button(top,text="Import NIC Master",command=lambda:self.load_master("industry")).pack(side=tk.RIGHT,padx=3)
        ttk.Button(top,text="Import NCO Master",command=lambda:self.load_master("occupation")).pack(side=tk.RIGHT,padx=3)
        ttk.Button(top,text="Export Mapping Review",command=self.export_mapping_review).pack(side=tk.RIGHT,padx=3)
        ttk.Label(tab,text="District is an internal key, not a file. Official LGD codes should replace internal keys in production.",foreground=Style.MUTED).pack(anchor="w",pady=5)
        self.mapping_tree=self.tree(tab,("type","raw","standard","code","status","confidence","method"),["Type","Raw","Standard","Code","Status","Confidence","Method"],[100,180,220,110,100,100,180])

    def _tab_curated(self,tab):
        top=ttk.Frame(tab); top.pack(fill=tk.X)
        ttk.Label(top,text="Curated Data Model",style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(top,text="Build Curated Tables",command=self.build_curated).pack(side=tk.RIGHT)
        self.curated_tree=self.tree(tab,("table","rows","description"),["Curated Table","Rows","Purpose"],[200,100,700])
        note=ScrolledText(tab,height=8,font=("Consolas",9),bg="white",relief="flat"); note.pack(fill=tk.X,pady=8)
        note.insert("1.0",
            "training_supply:\n  district_id, institution_id, course_code, occupation_code, year, capacity, completions, placed\n\n"
            "skill_demand:\n  district_id, industry_code, occupation_code, year, vacancies, wage\n\n"
            "economic_activity:\n  district_id, industry_code, year, enterprise_count, employment, wage\n\n"
            "labour_supply:\n  district_id, occupation_code, year, labour_force, employed, unemployed, formal_employment\n\n"
            "curated_fact:\n  harmonised facts with source file lineage.\n")
        note.configure(state="disabled")

    def _tab_intel(self,tab):
        top=ttk.Frame(tab); top.pack(fill=tk.X)
        ttk.Label(top,text="Skill Gap Engine",style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(top,text="Compute",style="Primary.TButton",command=self.compute_intelligence).pack(side=tk.RIGHT)
        ttk.Label(tab,text="Gap = demand − usable supply. Supply method is explicitly shown so proxies are not hidden.",foreground=Style.MUTED).pack(anchor="w",pady=5)
        self.intel_tree=self.tree(tab,
            ("district","industry","occupation","records","supply","supply_method","demand","gap","gap_pct","confidence","signal"),
            ["District","Industry","Occupation","Records","Supply","Supply Method","Demand","Gap","Gap %","Confidence","Signal"],
            [140,160,190,70,90,120,90,90,80,90,150])
        self.rec_text=ScrolledText(tab,height=9,font=("Segoe UI",9),bg="white",relief="flat"); self.rec_text.pack(fill=tk.X,pady=8)

    def _tab_lineage(self,tab):
        top=ttk.Frame(tab); top.pack(fill=tk.X)
        ttk.Label(top,text="Data Lineage",style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(top,text="Export Audit Log",command=self.export_audit).pack(side=tk.RIGHT)
        self.lineage_text=ScrolledText(tab,font=("Consolas",9),bg="white",relief="flat"); self.lineage_text.pack(fill=tk.BOTH,expand=True)
        self.lineage_text.insert("1.0",
            "Traceability concept:\n\nSkill Gap\n  ↓\nDemand / Supply inputs\n  ↓\nCurated tables\n  ↓\nSource file_id(s)\n  ↓\nRaw stored artifact\n  ↓\nOriginal source path / URL in the input data\n\n"
            "The prototype keeps immutable raw copies in runtime/raw_store and file metadata in runtime/ksisu.db.\n"
            "Use Export Source Registry + Export Intelligence to demonstrate traceability.\n")
        self.lineage_text.configure(state="disabled")

    def _tab_reference(self,tab):
        text=ScrolledText(tab,font=("Segoe UI",9),bg="white",relief="flat",padx=14,pady=14); text.pack(fill=tk.BOTH,expand=True)
        ref = """KSISU REFERENCE — IMPLEMENTED ARCHITECTURE

DATA SOURCES
• Government departments, Central Government, industry, surveys
• Excel / CSV / JSON / HTML connectors
• 31 district Excel files in this package are simulated source artifacts, not the production architecture.

INGESTION + RAW
• File discovery is recursive.
• Each artifact gets file_id, checksum, version, schema, record count, period, district hint, privacy/status.
• The original input is copied to runtime/raw_store and is not overwritten.
• Source registry is stored in runtime/ksisu.db.

DATA CATALOG
• source_files: metadata and lineage.
• schema_maps: source column → canonical field.
• processing_runs / audit log support reproducibility.

QUALITY
• Missingness, exact duplicates, near-duplicate review, basic validity/uniqueness checks.
• Per-file quality scores are visible.

HARMONISATION
• District → LGD
• Occupation → NCO
• Industry → NIC
• Official masters should be loaded for production. Demo aliases are clearly marked.

CURATED LAYER
• training_supply
• skill_demand
• economic_activity
• labour_supply
• curated_fact
These become connected analytical tables using district_id / occupation_code / industry_code.

INTELLIGENCE
• District × industry × occupation groups.
• Demand − supply gap.
• Supply method is explicit: direct_supply / completions / training_capacity / unavailable.
• Confidence reflects completeness, mapping confidence and record count.
• Recommendations are human-review suggestions, not automatic policy decisions.

KSI
• The official KSI formula is not claimed by this prototype. The tool produces the harmonised indicators and evidence that could feed the eventual index.

IMPORTANT
• Numeric values in the bundled 31-district files are synthetic demo values.
• Public company/entity names may appear because they were collected for demo realism; that does not make the associated metrics official.
"""
        text.insert("1.0",ref); text.configure(state="disabled")

    def set_status(self,msg):
        self.status.set(msg); self.root.update_idletasks()

    def refresh_all(self):
        self.refresh_registry(); self.refresh_quality(); self.refresh_schema(); self.refresh_mapping(); self.refresh_curated(); self.refresh_intel(); self.refresh_kpis()

    def refresh_registry(self):
        if not hasattr(self,"registry_tree"): return
        self.registry_tree.delete(*self.registry_tree.get_children())
        cols=[d[1] for d in self.engine.registry.conn.execute("PRAGMA table_info(source_files)").fetchall()]
        for row in self.engine.registry.rows():
            r=dict(zip(cols,row))
            self.registry_tree.insert("",tk.END,values=(r["file_id"],r["source_name"],r["dataset_name"],r["district_hint"],r["format"],r["record_count"],r["checksum"][:10],r["version"],r["privacy_level"],r["status"]))

    def refresh_quality(self):
        if not hasattr(self,"quality_tree"): return
        self.quality_tree.delete(*self.quality_tree.get_children())
        q=self.engine.quality or {}
        if not q:
            self.quality_tree.insert("",tk.END,values=("Status","0","Ingest data first.")); return
        meanings={
            "Rows":"Records in the current in-memory analytical frame.",
            "Columns":"Canonical + preserved raw lineage fields.",
            "Exact duplicates":"Exact repeats suitable for first-pass removal.",
            "Near duplicate groups":"Similarity groups requiring review.",
            "Missing district":"Records not linked to a district.",
            "Missing occupation":"Records missing occupation/job/trade evidence.",
            "Missing industry":"Records missing industry evidence.",
            "Missing demand":"Rows with no demand metric.",
            "Missing supply":"Rows with no direct supply metric."
        }
        for k,v in q.items(): self.quality_tree.insert("",tk.END,values=(k,v,meanings.get(k,"")))
        self.quality_text.delete("1.0",tk.END)
        self.quality_text.insert("1.0",self.quality_summary())

    def quality_summary(self):
        q=self.engine.quality or {}
        if not q: return ""
        rows=q.get("Rows",0)
        completeness=1-(q.get("Missing district",0)+q.get("Missing occupation",0)+q.get("Missing industry",0))/max(1,rows*3)
        uniqueness=1-q.get("Exact duplicates",0)/max(1,rows)
        validity=1-(q.get("Missing demand",0)+q.get("Missing supply",0))/max(1,rows*2)
        score=100*(0.30*completeness+0.30*uniqueness+0.20*validity+0.20)
        return f"QUALITY SCORE: {score:.1f}%\nCompleteness: {completeness*100:.1f}%\nUniqueness: {uniqueness*100:.1f}%\nBasic validity: {validity*100:.1f}%\n\nRule: this is a prototype data-quality score, not an official KSISU standard."

    def refresh_schema(self):
        if not hasattr(self,"schema_tree"): return
        self.schema_tree.delete(*self.schema_tree.get_children())
        for r in self.engine.registry.schema_rows():
            self.schema_tree.insert("",tk.END,values=(r[0],r[1],r[2],f"{float(r[3]):.2f}",r[4]))

    def refresh_mapping(self):
        if not hasattr(self,"mapping_tree"): return
        self.mapping_tree.delete(*self.mapping_tree.get_children())
        if self.engine.df.empty: return
        for kind,src,std,code,status,conf,method in [
            ("District","district","district_standard","lgd_code","district_map_status","district_map_confidence","district_map_method"),
            ("Industry","industry_name","industry_standard","nic_standard_code","industry_map_status","industry_map_confidence","industry_map_method"),
            ("Occupation","occupation","occupation_standard","nco_standard_code","occupation_map_status","occupation_map_confidence","occupation_map_method")
        ]:
            if src not in self.engine.df.columns or std not in self.engine.df.columns: continue
            sub=self.engine.df[[src,std,code,status,conf,method]].drop_duplicates().head(400)
            for _,r in sub.iterrows():
                self.mapping_tree.insert("",tk.END,values=(kind,clean_text(r[src]),clean_text(r[std]),clean_text(r[code]),clean_text(r[status]),f"{float(r[conf]):.2f}" if pd.notna(r[conf]) else "",clean_text(r[method])))

    def refresh_curated(self):
        if not hasattr(self,"curated_tree"): return
        self.curated_tree.delete(*self.curated_tree.get_children())
        for name,desc in [
            ("training_supply","Local training / completion / placement supply"),
            ("skill_demand","Demand / vacancy signals by district / industry / occupation"),
            ("economic_activity","Entity and employment activity by district / industry"),
            ("labour_supply","Labour and formal employment signals"),
            ("curated_fact","Harmonised fact table with lineage")
        ]:
            p=CURATED_DIR/f"{name}.csv"
            rows=len(pd.read_csv(p)) if p.exists() else 0
            self.curated_tree.insert("",tk.END,values=(name,rows,desc))

    def refresh_intel(self):
        if not hasattr(self,"intel_tree"): return
        self.intel_tree.delete(*self.intel_tree.get_children())
        self.rec_text.delete("1.0",tk.END)
        if self.engine.last_intelligence.empty:
            self.rec_text.insert("1.0","No intelligence computed yet.")
            return
        for _,r in self.engine.last_intelligence.head(500).iterrows():
            self.intel_tree.insert("",tk.END,values=(r.get("district",""),r.get("industry",""),r.get("occupation",""),r.get("records",""),r.get("supply",""),r.get("supply_method",""),r.get("demand",""),r.get("gap",""),r.get("gap_pct",""),r.get("confidence",""),r.get("signal","")))
        for r in self.engine.last_recommendations[:200]:
            self.rec_text.insert(tk.END,f"[{r['confidence']}] {r['district']} / {r['industry']} / {r['occupation']}\n{r['signal']}\n{r['recommendation']}\n\n")

    def refresh_kpis(self):
        q=self.engine.quality or {}
        self.kpis["sources"].set(str(len(self.discovered)))
        self.kpis["ingested"].set(str(len(self.engine.registry.rows())))
        self.kpis["rows"].set(str(q.get("Rows",0)))
        self.kpis["quality"].set(self.quality_score_text())
        mapped=0
        if not self.engine.df.empty and "district_map_status" in self.engine.df:
            mapped=int((self.engine.df["district_map_status"]=="mapped").sum())
        self.kpis["mapped"].set(str(mapped))
        alerts=int(self.engine.last_intelligence["signal"].astype(str).str.contains("GAP",na=False).sum()) if not self.engine.last_intelligence.empty else 0
        self.kpis["alerts"].set(str(alerts))

    def quality_score_text(self):
        q=self.engine.quality or {}
        if not q or not q.get("Rows"): return "0%"
        rows=q["Rows"]
        c=1-(q.get("Missing district",0)+q.get("Missing occupation",0)+q.get("Missing industry",0))/max(1,rows*3)
        u=1-q.get("Exact duplicates",0)/max(1,rows)
        v=1-(q.get("Missing demand",0)+q.get("Missing supply",0))/max(1,rows*2)
        return f"{100*(0.3*c+0.3*u+0.2*v+0.2):.0f}%"

    def discover_sources(self):
        self.discovered=self.engine.discover()
        self.refresh_kpis(); self.refresh_registry()
        self.set_status(f"Discovered {len(self.discovered)} source artifacts.")
        self.nb.select(self.tabs[0])

    def load_schema_overrides(self):
        path=filedialog.askopenfilename(title="Select schema override CSV",filetypes=[("CSV","*.csv")])
        if not path: return
        try:
            n=self.engine.load_schema_overrides(path)
            self.engine.audit_log("SCHEMA_OVERRIDES",f"rows={n};file={path}")
            self.set_status(f"Loaded {n} schema override rules. Re-ingest sources to apply them.")
            messagebox.showinfo("Schema overrides loaded",f"{n} rules loaded. Run Ingest All Discovered again to apply them.")
        except Exception as e:
            messagebox.showerror("Schema override import failed",str(e))

    def ingest_all(self):
        """Ingest discovered source files on the Tkinter main thread.

        The previous implementation launched ingestion in a background thread while
        reusing the Registry's SQLite connection created by the Tkinter thread.
        Python's sqlite3 driver correctly rejected that cross-thread use.
        Ingestion is intentionally kept synchronous here because the bundled demo
        contains only a small number of source artifacts; this guarantees that the
        SQLite connection and all UI state remain on one thread.
        """
        if not self.discovered:
            self.discovered=self.engine.discover()
        if not self.discovered:
            messagebox.showwarning("No sources found", "No supported source files were discovered in the configured input folder.")
            return
        self.set_status(f"Ingesting {len(self.discovered)} source artifacts…")
        self.root.update_idletasks()
        try:
            files,rows=self.engine.ingest(self.discovered)
            self.engine.audit_log("INGEST",f"files={files};rows={rows}")
            self.after_action(f"Ingested {files} artifacts / {rows} rows.",0)
            messagebox.showinfo("Ingestion complete", f"Source artifacts ingested: {files}\nRecords loaded: {rows}")
        except Exception as e:
            self.set_status("Ingestion failed")
            messagebox.showerror("Ingestion failed", f"{type(e).__name__}: {e}")

    def after_action(self,msg,tab_index=None):
        self.refresh_all(); self.set_status(msg)
        if tab_index is not None: self.nb.select(self.tabs[tab_index])

    def run_quality(self):
        self.engine.run_quality(); self.engine.audit_log("QUALITY","Quality checks refreshed")
        self.after_action("Quality checks completed.",1)

    def drop_exact(self):
        n=self.engine.deduplicate(False); self.engine.audit_log("DEDUPLICATE",f"removed={n}")
        self.after_action(f"Removed {n} exact duplicate rows.",1)

    def show_near(self):
        if not self.engine.near_dupes:
            messagebox.showinfo("Near duplicates","No near-duplicate groups detected in the current frame.")
            return
        text="\n".join([f"Group {i+1}: score={g['score']:.2f} rows={g['indexes']}" for i,g in enumerate(self.engine.near_dupes[:100])])
        messagebox.showinfo("Near-duplicate review",text)

    def load_demo_masters(self):
        files={"district":BASE_DIR/"examples/demo_masters/demo_lgd_master.csv",
               "industry":BASE_DIR/"examples/demo_masters/demo_nic_master.csv",
               "occupation":BASE_DIR/"examples/demo_masters/demo_nco_master.csv"}
        try:
            counts=[]
            for kind,path in files.items():
                counts.append(self.engine.mapping_engine.import_master(kind,path))
            if not self.engine.df.empty:
                self.engine.harmonise()
            self.engine.audit_log("DEMO_MASTERS",json.dumps(counts))
            self.after_action(f"Loaded demo-only LGD/NIC/NCO masters: {counts}.",3)
        except Exception as e:
            messagebox.showerror("Demo master import failed",str(e))

    def load_master(self,kind):
        path=filedialog.askopenfilename(title=f"Select {kind} master",filetypes=[("CSV / Excel","*.csv *.xlsx *.xls")])
        if not path: return
        try:
            n=self.engine.mapping_engine.import_master(kind,path)
            self.engine.harmonise() if not self.engine.df.empty else None
            self.engine.audit_log("MASTER_IMPORT",f"{kind}={path};rows={n}")
            self.after_action(f"Loaded {n} {kind} mappings.",3)
        except Exception as e:
            messagebox.showerror("Master import failed",str(e))

    def harmonise(self):
        if self.engine.df.empty:
            messagebox.showwarning("No data","Ingest source files first."); return
        self.engine.harmonise(); self.engine.audit_log("HARMONISE","LGD/NIC/NCO mapping applied")
        self.after_action("Harmonisation complete.",3)

    def build_curated(self):
        if self.engine.df.empty:
            messagebox.showwarning("No data","Ingest source files first."); return
        result=self.engine.build_curated(); self.engine.audit_log("CURATED",json.dumps(result))
        self.after_action("Curated analytical tables built.",4)

    def compute_intelligence(self):
        if self.engine.df.empty:
            messagebox.showwarning("No data","Ingest source files first."); return
        r=self.engine.compute_intelligence(); self.engine.audit_log("INTELLIGENCE",f"groups={len(r)}")
        self.after_action(f"Computed {len(r)} district/industry/occupation groups.",5)

    def export_registry(self):
        ensure_dirs()
        path=EXPORT_DIR/"source_registry.csv"; self.engine.registry.export_csv(path)
        messagebox.showinfo("Export complete",str(path))

    def export_schema(self):
        path=EXPORT_DIR/"schema_mapping.csv"; self.engine.export_schema_map(path)
        messagebox.showinfo("Export complete",str(path))

    def export_mapping_review(self):
        path=EXPORT_DIR/"mapping_review.csv"; self.engine.export_mapping_review(path)
        messagebox.showinfo("Export complete",str(path))

    def export_audit(self):
        p=AUDIT_DIR/"processing_log.jsonl"
        if not p.exists(): p.write_text("",encoding="utf-8")
        messagebox.showinfo("Audit log",str(p))

    def export_bundle(self):
        ensure_dirs()
        self.engine.registry.export_csv(EXPORT_DIR/"source_registry.csv")
        self.engine.export_schema_map(EXPORT_DIR/"schema_mapping.csv")
        self.engine.export_mapping_review(EXPORT_DIR/"mapping_review.csv")
        if not self.engine.df.empty: self.engine.export_cleaned(EXPORT_DIR/"harmonised_data.csv")
        if not self.engine.last_intelligence.empty: self.engine.export_intelligence(EXPORT_DIR/"skill_gap_intelligence.csv")
        report={
            "generated_at":datetime.now().isoformat(timespec="seconds"),
            "sources_discovered":len(self.discovered),
            "files_ingested":len(self.engine.registry.rows()),
            "records":int(len(self.engine.df)),
            "quality":self.engine.quality,
            "note":self.engine.last_ksi_note
        }
        (EXPORT_DIR/"run_summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        self.engine.audit_log("EXPORT_BUNDLE","exports written")
        messagebox.showinfo("Export bundle",f"Exports written to:\n{EXPORT_DIR}")

    def show_selected_source(self):
        pass

    def run(self):
        self.root.mainloop()

if __name__=="__main__":
    try:
        App().run()
    except Exception as exc:
        root=tk.Tk(); root.withdraw()
        messagebox.showerror(APP_TITLE,str(exc))
        root.destroy()
