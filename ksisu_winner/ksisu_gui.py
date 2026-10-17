from __future__ import annotations

from pathlib import Path
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from run_gap import ROOT, RAW, CLEAN, OUT, CONFIG, compute_model


class KSISUGUI(tk.Tk):
    """Judge-facing GUI: no fake data entry; user supplies real district ITI evidence."""

    def __init__(self):
        super().__init__()
        self.title("KSISU Real-Data Evidence Workbench")
        self.geometry("1450x920")
        self.minsize(1180, 760)
        self.configure(bg="#eef3f9")
        self.actual_supply = None
        self.last = None
        self.proxy_last = None

        self.status = tk.StringVar(value="Ready — proxy mode is the conservative default.")
        self.open_low = tk.StringVar(value=str(CONFIG["opening_rate"]["low"]))
        self.open_mode = tk.StringVar(value=str(CONFIG["opening_rate"]["mode"]))
        self.open_high = tk.StringVar(value=str(CONFIG["opening_rate"]["high"]))
        self.fill_low = tk.StringVar(value=str(CONFIG["seat_fill_rate"]["low"]))
        self.fill_mode = tk.StringVar(value=str(CONFIG["seat_fill_rate"]["mode"]))
        self.fill_high = tk.StringVar(value=str(CONFIG["seat_fill_rate"]["high"]))
        self.comp_low = tk.StringVar(value=str(CONFIG["completion_rate"]["low"]))
        self.comp_mode = tk.StringVar(value=str(CONFIG["completion_rate"]["mode"]))
        self.comp_high = tk.StringVar(value=str(CONFIG["completion_rate"]["high"]))
        self.entry_low = tk.StringVar(value=str(CONFIG["sector_entry_rate"]["low"]))
        self.entry_mode = tk.StringVar(value=str(CONFIG["sector_entry_rate"]["mode"]))
        self.entry_high = tk.StringVar(value=str(CONFIG["sector_entry_rate"]["high"]))
        self.seed = tk.StringVar(value=str(CONFIG["random_seed"]))
        self.draws = tk.StringVar(value=str(CONFIG["monte_carlo_draws"]))
        self.supply_path = tk.StringVar(value="")

        self._style()
        self._header()
        self._tabs()
        self._refresh_inputs()

    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground="#0d2a4a", background="#eef3f9")
        s.configure("Sub.TLabel", font=("Segoe UI", 9), foreground="#4d6380", background="#eef3f9")
        s.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=8)
        s.configure("TButton", padding=6)
        s.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _header(self):
        head = tk.Frame(self, bg="#0d2a4a", height=100)
        head.pack(fill="x")
        tk.Label(head, text="KSISU Real-Data Evidence Workbench", font=("Segoe UI", 20, "bold"), fg="white", bg="#0d2a4a").pack(anchor="w", padx=18, pady=(12, 2))
        tk.Label(head, text="Ingest → Harmonise → Demand proxy → ITI evidence → Shared Monte Carlo → Alignment → VOI → Human review", font=("Segoe UI", 9), fg="#cfe1ff", bg="#0d2a4a").pack(anchor="w", padx=18, pady=(0, 10))

        bar = tk.Frame(self, bg="#e6eef7")
        bar.pack(fill="x")
        ttk.Button(bar, text="Run Proxy Baseline", style="Primary.TButton", command=self.run_proxy).pack(side="left", padx=8, pady=8)
        ttk.Button(bar, text="Load Official NCVT Sample", command=self.load_bundled_sample).pack(side="left", padx=3, pady=8)
        ttk.Button(bar, text="Load Real District Supply CSV", command=self.load_real_supply).pack(side="left", padx=3, pady=8)
        ttk.Button(bar, text="Run With Loaded Supply", command=self.run_actual).pack(side="left", padx=3, pady=8)
        ttk.Button(bar, text="Run 3-Min Judge Demo", command=self.run_judge_demo).pack(side="left", padx=3, pady=8)
        ttk.Button(bar, text="Open Output", command=self.open_output).pack(side="left", padx=3, pady=8)
        tk.Label(bar, textvariable=self.status, bg="#e6eef7", fg="#29425f", anchor="w").pack(side="left", padx=12, fill="x", expand=True)

    def _tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.t_inputs = ttk.Frame(self.nb)
        self.t_results = ttk.Frame(self.nb)
        self.t_priority = ttk.Frame(self.nb)
        self.t_sens = ttk.Frame(self.nb)
        self.t_val = ttk.Frame(self.nb)
        self.t_demo = ttk.Frame(self.nb)
        for t, title in [(self.t_inputs,"1. Inputs & Assumptions"),(self.t_results,"2. Gap Results"),(self.t_priority,"3. District Priority"),(self.t_sens,"4. Sensitivity"),(self.t_val,"5. Validation & Linkage"),(self.t_demo,"6. Judge Demo")]:
            self.nb.add(t, text=title)
        self._inputs_tab(); self._results_tab(); self._priority_tab(); self._sens_tab(); self._validation_tab(); self._demo_tab()

    def _inputs_tab(self):
        left = ttk.LabelFrame(self.t_inputs, text="Research inputs", padding=8)
        left.pack(side="left", fill="both", expand=True, padx=(0,6), pady=6)
        self.source_tree = ttk.Treeview(left, columns=("source","file","grain","year"), show="headings")
        for c,t,w in [("source","Source","190"),("file","Local file","410"),("grain","Grain","150"),("year","Period","110")]:
            self.source_tree.heading(c,text=t); self.source_tree.column(c,width=w)
        self.source_tree.pack(fill="both", expand=True)
        note = tk.Label(left, text="All bundled source rows are public research inputs or explicitly labelled analyst priors. No synthetic company/metric pairings are used.", bg="#fff8df", fg="#5b4b20", justify="left", wraplength=760, padx=10, pady=10)
        note.pack(fill="x", pady=(8,0))

        right = ttk.LabelFrame(self.t_inputs, text="Model controls", padding=8)
        right.pack(side="right", fill="y", padx=(6,0), pady=6)
        ttk.Label(right, text="Scope: Manufacturing / NCO 72, 74", font=("Segoe UI",10,"bold")).pack(anchor="w", pady=(0,8))
        self._rate_inputs(right, "Opening rate", self.open_low, self.open_mode, self.open_high)
        self._rate_inputs(right, "Seat fill rate", self.fill_low, self.fill_mode, self.fill_high)
        self._rate_inputs(right, "Completion rate", self.comp_low, self.comp_mode, self.comp_high)
        self._rate_inputs(right, "Sector entry", self.entry_low, self.entry_mode, self.entry_high)
        self._rate_inputs(right, "MC draws / seed", self.draws, self.seed, None, single=True)
        ttk.Separator(right).pack(fill="x", pady=10)
        ttk.Label(right, text="District-actual supply", font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.supply_label = ttk.Label(right, text="Not loaded", wraplength=330)
        self.supply_label.pack(anchor="w", pady=6)
        ttk.Button(right, text="Load real CSV...", command=self.load_real_supply).pack(fill="x")
        ttk.Button(right, text="Use bundled official partial sample", command=self.load_bundled_sample).pack(fill="x", pady=4)
        ttk.Button(right, text="Clear actual supply", command=self.clear_supply).pack(fill="x")
        ttk.Label(right, text="Accepted columns:\ndistrict, seats + either nco_group_2digit or trade\n\nThe model never invents district seats.", foreground="#475c76", justify="left").pack(anchor="w", pady=10)

    def _rate_inputs(self, parent, label, a, b, c, single=False):
        row=ttk.Frame(parent); row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=19).pack(side="left")
        ttk.Entry(row,textvariable=a,width=9).pack(side="left",padx=2)
        ttk.Label(row,text="mode" if not single else "seed").pack(side="left")
        if b is not None:
            ttk.Entry(row,textvariable=b,width=9).pack(side="left",padx=2)
        if c is not None:
            ttk.Entry(row,textvariable=c,width=9).pack(side="left",padx=2)

    def _results_tab(self):
        self.results_note = tk.StringVar(value="Run the model. Policy-facing decisions are gated by evidence coverage.")
        ttk.Label(self.t_results, textvariable=self.results_note, font=("Segoe UI",10,"bold")).pack(anchor="w", padx=6, pady=6)
        self.results_tree = self._tree(self.t_results, [
            ("district","District",140),("group","NCO",55),("occupation","Occupation",250),
            ("p10","P10",75),("median","Median",80),("p90","P90",75),("width","Width",75),
            ("confidence","Evidence",80),("decision","Policy status",145),("basis","Supply basis",190)
        ])

    def _priority_tab(self):
        self.priority_tree = self._tree(self.t_priority,[
            ("rank","Priority",60),("district","District",160),("sci","SCI",80),("relative","Rel. to median",105),("openings","Openings",115),
            ("voi","VOI",115),("priority","Data priority",120),("confidence","Evidence",95),("actual","Full actual",90),("needs","Needs data",90)
        ])
        ttk.Label(self.t_priority,text="VOI = interval width × annual openings. Data priority also discounts already-strong evidence, so this is not simply a population ranking.",wraplength=1200).pack(fill="x",padx=6,pady=5)

    def _sens_tab(self):
        self.sens_text=tk.Text(self.t_sens,height=7,wrap="word")
        self.sens_text.pack(fill="x",padx=6,pady=6)
        self.sens_tree=self._tree(self.t_sens,[("district","District",150),("rank","Base rank",85),("p10","Rank P10",85),("median","Rank median",95),("p90","Rank P90",85),("top5","Top-5 frequency",110),("rho","Global rho",90)])

    def _validation_tab(self):
        self.val_text=tk.Text(self.t_val,height=9,wrap="word")
        self.val_text.pack(fill="x",padx=6,pady=6)
        self.val_tree=self._tree(self.t_val,[("metric","Metric",300),("value","Value",230),("status","Status",170)])

    def _demo_tab(self):
        txt=tk.Text(self.t_demo,wrap="word",font=("Segoe UI",10),bg="white")
        txt.pack(fill="both",expand=True,padx=6,pady=6)
        text='''JUDGE DEMO - USE THIS ORDER

1. Run Proxy Baseline. Say: "This is what KSISU can infer before complete district ITI supply is available. Mathematical ratios are shown, but policy status remains NEEDS DATA."

2. Open District Priority. Use SCI and VOI only as a data-collection prioritisation view; do not call the proxy ranking a district skill-gap finding.

3. Click Load Official NCVT Sample. The bundled File 1171 rows are an indexed partial sample for Tumakuru and Kalaburagi - not a downloaded complete district extract.

4. Click Run With Loaded Supply. Explain the partial-floor logic: observed seats are treated as a lower bound plus an uncertain remainder. The interval may widen. That is an honest evidence update, not fake precision.

5. For the final competition demo, load a complete district x trade NCVT/DGT/Karnataka file marked coverage_status=full_district_extract. The gate then allows a provisional policy call only when all 31 districts and modeled groups are covered.

6. Open Sensitivity. Show rank stability across the shared Monte Carlo draws rather than a chart that merely reflects arbitrary parameter range widths.

7. Open Validation & Linkage. Show 80 seeded typos, 20 unseen aliases routed to review, a real duplicate-removal pass, and the source lineage fields.

THE ONE-SENTENCE STORY
"We do not force a district gap decision when public data cannot support it; we quantify the uncertainty, show which evidence changes the result, and tell KSISU where to collect better district data first."
'''
        txt.insert('1.0',text); txt.configure(state='disabled')

    def _tree(self,parent, cols):
        frame=ttk.Frame(parent); frame.pack(fill="both",expand=True,padx=6,pady=6)
        tv=ttk.Treeview(frame,columns=[c[0] for c in cols],show="headings")
        for key,title,width in cols:
            tv.heading(key,text=title); tv.column(key,width=width,anchor="w" if key in {"district","occupation","basis","parameter","metric"} else "center")
        y=ttk.Scrollbar(frame,orient="vertical",command=tv.yview); x=ttk.Scrollbar(frame,orient="horizontal",command=tv.xview)
        tv.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        tv.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns"); x.grid(row=1,column=0,sticky="ew")
        frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1)
        return tv

    def _refresh_inputs(self):
        for item in self.source_tree.get_children(): self.source_tree.delete(item)
        files=[
            ("LGD district register",RAW/"lgd_districts.csv","district","2026"),
            ("Udyam district employment",RAW/"karnataka_udyam_employment_nov2022.csv","district","2022"),
            ("ASI manufacturing base",RAW/"asi_karnataka_manufacturing_2022_23.csv","state","2022-23"),
            ("NCVT state ITI magnitude",RAW/"ncvtmis_karnataka_state_2022.csv","state","2022"),
            ("DGT historical division rates",RAW/"iti_division_training_2020_21.csv","division","2020-21"),
            ("NCVT File 1171 real partial",RAW/"ncvtmis_file1171_real_partial.csv","district×trade","historical"),
            ("Occupation prior",CLEAN/"occupation_mix_prior.csv","state prior","2022-23"),
            ("Human-reviewed course→NCO crosswalk",CLEAN/"crosswalk.csv","course→NCO","versioned")
        ]
        for name,p,g,y in files:
            self.source_tree.insert("","end",values=(name,str(p.relative_to(ROOT)),g,y))

    def _override_config(self):
        return {
            "opening_rate":{"low":float(self.open_low.get()),"mode":float(self.open_mode.get()),"high":float(self.open_high.get())},
            "seat_fill_rate":{"low":float(self.fill_low.get()),"mode":float(self.fill_mode.get()),"high":float(self.fill_high.get())},
            "completion_rate":{"low":float(self.comp_low.get()),"mode":float(self.comp_mode.get()),"high":float(self.comp_high.get())},
            "sector_entry_rate":{"low":float(self.entry_low.get()),"mode":float(self.entry_mode.get()),"high":float(self.entry_high.get())},
            "random_seed":int(self.seed.get()),"monte_carlo_draws":int(self.draws.get())
        }

    def run_proxy(self):
        try:
            self.status.set("Running proxy baseline..."); self.update_idletasks()
            self.proxy_last=compute_model(overrides=self._override_config())
            self.last=self.proxy_last
            self._display(self.last,"Proxy baseline complete — policy status is conservatively gated to NEEDS DATA.")
        except Exception as e:
            messagebox.showerror("Analysis failed",str(e)); self.status.set("Analysis failed")

    def run_actual(self):
        if not self.actual_supply:
            messagebox.showinfo("No district supply loaded","Load a real NCVT MIS / DGT / Karnataka district×trade seat CSV first.")
            return
        try:
            self.status.set("Running with loaded district supply..."); self.update_idletasks()
            self.last=compute_model(actual_supply_path=str(self.actual_supply),overrides=self._override_config())
            self._display(self.last,"Evidence-upgrade run complete — partial evidence remains NEEDS DATA until full district coverage is loaded.")
        except Exception as e:
            messagebox.showerror("Analysis failed",str(e)); self.status.set("Analysis failed")

    def run_judge_demo(self):
        try:
            self.status.set("Running 3-minute judge demo: proxy baseline → official partial NCVT evidence...")
            self.update_idletasks()
            self.proxy_last = compute_model(overrides=self._override_config())
            self.actual_supply = RAW / "ncvtmis_file1171_real_partial.csv"
            self.supply_path.set(str(self.actual_supply))
            self.supply_label.config(text=f"Bundled indexed NCVT sample loaded:\n{self.actual_supply.name}\nTumakuru + Kalaburagi; partial evidence only.")
            self.last = compute_model(actual_supply_path=str(self.actual_supply), overrides=self._override_config())
            self._display(self.last, "Judge demo complete — proxy vs real-evidence interval change is ready to show.")
            self.nb.select(self.t_demo)
        except Exception as e:
            messagebox.showerror("Judge demo failed", str(e))
            self.status.set("Judge demo failed")

    def load_bundled_sample(self):
        p=RAW/"ncvtmis_file1171_real_partial.csv"
        self.actual_supply=p
        self.supply_path.set(str(p))
        self.supply_label.config(text=f"Bundled indexed NCVT sample loaded:\n{p.name}\nTumakuru + Kalaburagi; 9 indexed rows; incomplete district coverage.")
        self.status.set("Bundled official partial NCVT sample selected. Click Run With Loaded Supply.")

    def load_real_supply(self):
        p=filedialog.askopenfilename(title="Choose real district×trade ITI supply CSV",filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if p:
            self.actual_supply=Path(p); self.supply_path.set(str(p)); self.supply_label.config(text=f"Loaded:\n{p}"); self.status.set("Real district supply selected. Click Run With Loaded Supply.")

    def clear_supply(self):
        self.actual_supply=None; self.supply_path.set(""); self.supply_label.config(text="Not loaded — proxy mode")
        self.status.set("District supply cleared; proxy baseline selected.")

    def _display(self,res,msg):
        r=res["ratio"]; d=res["district"]; s=res["sensitivity"]; c=res["corruption"]
        self.status.set(msg)
        self.results_note.set(f"{len(d)} districts × {r.nco_group_2digit.nunique()} NCO groups • {r.decision_status.value_counts().to_dict()} • Actual supply loaded: {res['audit']['actual_supply_loaded']}")
        self._fill(self.results_tree, r, lambda x:(x.district,x.nco_group_2digit,x.occupation_label,f"{x.ratio_p10:.3f}",f"{x.ratio_median:.3f}",f"{x.ratio_p90:.3f}",f"{x.interval_width:.3f}",f"{x.confidence_score:.2f}",x.decision_status,x.supply_basis))
        self._fill(self.priority_tree, d, lambda x:(x.priority_rank,x.district,f"{x.SCI:.3f}",f"{x.relative_SCI_vs_state_median:.2f}x",f"{x.total_annual_openings:,.0f}",f"{x.VOI:,.0f}",f"{x.data_collection_priority:,.0f}",f"{x.mean_confidence:.2f}",x.actual_cells,x.needs_data_cells))
        self.sens_text.delete("1.0","end")
        self.sens_text.insert("1.0", "Sensitivity now reports rank stability across the shared Monte Carlo draws. This tests whether district priority is stable under common system-level uncertainty; it does not simply restate the width of arbitrary parameter ranges.\n")
        self._fill(self.sens_tree, s, lambda x:(x.district,int(x.baseline_rank),f"{x.rank_p10:.0f}",f"{x.rank_median:.0f}",f"{x.rank_p90:.0f}",f"{x.top5_frequency*100:.1f}%",f"{x.global_rank_stability_median_rho:.3f}"))
        self.val_text.delete("1.0","end")
        self.val_text.insert("1.0", "Corruption rows are never dropped; review rows remain visible. Source provenance is regenerated from the curated source registry and retains official URLs.\n")
        for item in self.val_tree.get_children(): self.val_tree.delete(item)
        rows=[
            ("District count",len(d),"PASS" if len(d)==31 else "REVIEW"),
            ("Seeded corruption test",f"{int(c.iloc[0].seeded_corruptions)} cases; {float(c.iloc[0].seeded_typo_recovery_rate)*100:.1f}% typo recovery","PASS" if float(c.iloc[0].seeded_typo_recovery_rate)>=0.9 else "REVIEW"),
            ("Unmatched review rows",int(c.iloc[0].unmatched_review_rows),"REVIEW QUEUE" if int(c.iloc[0].unmatched_review_rows)>0 else "PASS"),
            ("Selected occupation share",f"{res['audit']['occupation_share_sum_selected']:.2f}","72 + 74 only; not normalized"),
            ("Selected course weight",f"{res['audit']['selected_course_weight_sum']:.2f}","72 + 74 only; not normalized"),
            ("Monte Carlo draws",res['audit']['monte_carlo_draws'],"PASS"),
            ("Relative SCI", "SCI / statewide median", "PRIORITY INDEX"),
            ("Proxy allocation diagnostic",f"{res['audit'].get('district_supply_proxy_correlation',float('nan')):.3f}","NOT VALIDATION"),
        ]
        demo=res.get("interval_demo")
        if demo is not None and not demo.empty:
            rows.append(("Partial evidence update",f"{(demo.evidence_effect=='WIDER').sum()} cells widened; partial rows are floors + uncertain remainder","EVIDENCE UPDATE"))
        for row in rows: self.val_tree.insert("","end",values=row)

    def _fill(self,tv,df,fn):
        for i in tv.get_children(): tv.delete(i)
        if df is None or df.empty: return
        for _,row in df.iterrows(): tv.insert("","end",values=fn(row))

    def open_output(self):
        try:
            os.startfile(str(OUT))
        except Exception:
            messagebox.showinfo("Output folder",str(OUT))


if __name__ == "__main__":
    app=KSISUGUI(); app.mainloop()
