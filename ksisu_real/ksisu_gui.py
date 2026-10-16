from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from run_gap import ROOT, CLEAN, RAW, OUT, CONFIG, compute_model

class KSISUGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KSISU Real-Data Intelligence Pilot")
        self.geometry("1320x880")
        self.minsize(1100, 760)
        self.configure(bg="#f4f7fb")
        self.paths = {
            "lgd": RAW / "lgd_districts.csv",
            "employment": RAW / "karnataka_udyam_employment_nov2022.csv",
            "asi": RAW / "asi_karnataka_manufacturing_2022_23.csv",
            "ncvt": RAW / "ncvtmis_karnataka_state_2022.csv",
            "occupation_mix": CLEAN / "occupation_mix_prior.csv",
            "crosswalk": CLEAN / "crosswalk.csv",
            "dgt": RAW / "iti_division_training_2020_21.csv",
            "division_map": CLEAN / "district_dgt_division_map.csv",
        }
        self.actual_supply = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready. This pilot defaults to public research inputs and clearly labels proxy assumptions.")
        self.seed_var = tk.StringVar(value=str(CONFIG.get("random_seed", 20261016)))
        self.draws_var = tk.StringVar(value=str(CONFIG.get("monte_carlo_draws", 5000)))
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
        self.selected_groups = {g: tk.BooleanVar(value=True) for g in ["72", "74", "81"]}
        self._last_results = None
        self._baseline_ratio = None
        self._build_style()
        self._build_header()
        self._build_tabs()
        self._populate_source_tree()

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground="#0f2747", background="#f4f7fb")
        style.configure("Sub.TLabel", font=("Segoe UI", 9), foreground="#4d5f75", background="#f4f7fb")
        style.configure("Card.TLabelframe", background="#ffffff", bordercolor="#ccd6e4")
        style.configure("Card.TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground="#0f2747", background="#ffffff")
        style.configure("TButton", font=("Segoe UI", 9))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Status.TLabel", background="#0f2747", foreground="white", padding=6)

    def _build_header(self):
        top = tk.Frame(self, bg="#0f2747", height=85)
        top.pack(fill="x")
        tk.Label(top, text="KSISU Real-Data Intelligence Pilot", font=("Segoe UI", 20, "bold"), fg="white", bg="#0f2747").pack(anchor="w", padx=18, pady=(13, 0))
        tk.Label(top, text="Ingest → Registry → Harmonise → Manufacturing demand → ITI supply → Monte Carlo interval → Confidence → VOI → Human review", font=("Segoe UI", 9), fg="#cfe1ff", bg="#0f2747").pack(anchor="w", padx=18, pady=(2, 10))

        action = tk.Frame(self, bg="#eaf0f8")
        action.pack(fill="x")
        ttk.Button(action, text="Run Analysis", style="Primary.TButton", command=self.run_analysis).pack(side="left", padx=12, pady=8)
        ttk.Button(action, text="Load Actual District Supply", command=self.load_actual_supply).pack(side="left", padx=4)
        ttk.Button(action, text="Manual Supply Entry", command=self.manual_supply_entry).pack(side="left", padx=4)
        ttk.Button(action, text="Clear Actual Supply", command=self.clear_actual_supply).pack(side="left", padx=4)
        ttk.Button(action, text="Open Output", command=self.open_output).pack(side="left", padx=4)
        ttk.Button(action, text="Open README", command=self.open_readme).pack(side="left", padx=4)
        tk.Label(action, textvariable=self.status, bg="#eaf0f8", fg="#31455f", anchor="w").pack(side="left", padx=15, fill="x", expand=True)

    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_inputs = ttk.Frame(self.nb)
        self.tab_results = ttk.Frame(self.nb)
        self.tab_priority = ttk.Frame(self.nb)
        self.tab_sensitivity = ttk.Frame(self.nb)
        self.tab_validation = ttk.Frame(self.nb)
        self.tab_demo = ttk.Frame(self.nb)
        self.nb.add(self.tab_inputs, text="1. Inputs & Assumptions")
        self.nb.add(self.tab_results, text="2. Gap Results")
        self.nb.add(self.tab_priority, text="3. District Priority")
        self.nb.add(self.tab_sensitivity, text="4. Sensitivity")
        self.nb.add(self.tab_validation, text="5. Validation & Linkage")
        self.nb.add(self.tab_demo, text="6. Judge Demo")
        self._build_inputs_tab()
        self._build_results_tab()
        self._build_priority_tab()
        self._build_sensitivity_tab()
        self._build_validation_tab()
        self._build_demo_tab()

    def _build_inputs_tab(self):
        left = ttk.LabelFrame(self.tab_inputs, text="Source files", style="Card.TLabelframe")
        left.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=5)
        cols = ("name", "path", "grain")
        self.source_tree = ttk.Treeview(left, columns=cols, show="headings")
        self.source_tree.heading("name", text="Source")
        self.source_tree.heading("path", text="File")
        self.source_tree.heading("grain", text="Expected grain")
        self.source_tree.column("name", width=170)
        self.source_tree.column("path", width=470)
        self.source_tree.column("grain", width=140)
        self.source_tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(left, text="Change selected file", command=self.change_source).pack(anchor="e", padx=8, pady=(0, 8))

        right = ttk.Frame(self.tab_inputs)
        right.pack(side="right", fill="y", padx=(6, 0), pady=5)

        groups = ttk.LabelFrame(right, text="Question being tested", style="Card.TLabelframe")
        groups.pack(fill="x", pady=(0, 8))
        ttk.Label(groups, text="Manufacturing only. Compare ITI trade-linked supply against annual openings for NCO 72, 74 and 81.", wraplength=390).pack(anchor="w", padx=8, pady=8)
        for g, label in [("72", "72 - Metal / machinery trades"), ("74", "74 - Electrical / electronic trades"), ("81", "81 - Plant / machine operators")]:
            ttk.Checkbutton(groups, text=label, variable=self.selected_groups[g]).pack(anchor="w", padx=10, pady=2)

        rates = ttk.LabelFrame(right, text="Uncertainty ranges", style="Card.TLabelframe")
        rates.pack(fill="x", pady=8)
        self._rate_row(rates, "Openings rate", self.open_low, self.open_mode, self.open_high)
        self._rate_row(rates, "Seat fill rate", self.fill_low, self.fill_mode, self.fill_high)
        self._rate_row(rates, "Completion rate", self.comp_low, self.comp_mode, self.comp_high)
        self._rate_row(rates, "Sector entry", self.entry_low, self.entry_mode, self.entry_high)

        run = ttk.LabelFrame(right, text="Reproducibility", style="Card.TLabelframe")
        run.pack(fill="x", pady=8)
        self._small_entry(run, "Monte Carlo draws", self.draws_var)
        self._small_entry(run, "Random seed", self.seed_var)

        actual = ttk.LabelFrame(right, text="District-actual supply override", style="Card.TLabelframe")
        actual.pack(fill="x", pady=8)
        ttk.Label(actual, text="Optional CSV: district,nco_group_2digit,seats (or trade)", wraplength=390).pack(anchor="w", padx=8, pady=(8, 3))
        ent = ttk.Entry(actual, textvariable=self.actual_supply, width=52)
        ent.pack(side="left", padx=8, pady=8, fill="x", expand=True)
        ttk.Button(actual, text="Browse", command=self.load_actual_supply).pack(side="right", padx=8, pady=8)

        note = tk.Label(right, text="The built-in research run uses public sources. Empty district-actual supply means the app uses the explicitly labelled proxy. The moment you load district/trade seats, the same model switches those districts to district-actual and recomputes the interval.", justify="left", wraplength=410, bg="#fff8df", fg="#5b4b20", padx=10, pady=10)
        note.pack(fill="x", pady=8)

    def _small_entry(self, parent, label, var):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=5)
        ttk.Label(row, text=label, width=18).pack(side="left")
        ttk.Entry(row, textvariable=var, width=12).pack(side="left")

    def _rate_row(self, parent, label, low, mode, high):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text=label, width=18).pack(side="left")
        for v in [low, mode, high]:
            ttk.Entry(row, textvariable=v, width=8).pack(side="left", padx=3)

    def _build_results_tab(self):
        top = ttk.Frame(self.tab_results)
        top.pack(fill="x", pady=5)
        self.result_summary = tk.StringVar(value="Run the model to see results.")
        ttk.Label(top, textvariable=self.result_summary, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(top, text="Decision rule: GAP only when p90 < 1; SURPLUS only when p10 > 1; otherwise NEEDS DATA.").pack(anchor="w")
        cols = ("district", "group", "occupation", "p10", "median", "p90", "width", "confidence", "decision", "basis")
        self.results_tree = ttk.Treeview(self.tab_results, columns=cols, show="headings")
        headings = {"district":"District", "group":"NCO", "occupation":"Occupation", "p10":"P10", "median":"Median", "p90":"P90", "width":"Width", "confidence":"Confidence", "decision":"Decision", "basis":"Supply basis"}
        widths = {"district":145,"group":55,"occupation":245,"p10":70,"median":75,"p90":70,"width":70,"confidence":85,"decision":130,"basis":180}
        for c in cols:
            self.results_tree.heading(c, text=headings.get(c, c))
            self.results_tree.column(c, width=widths.get(c, 100), anchor="center" if c not in ["district","occupation","basis"] else "w")
        y=ttk.Scrollbar(self.tab_results, orient="vertical", command=self.results_tree.yview)
        x=ttk.Scrollbar(self.tab_results, orient="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.results_tree.pack(fill="both", expand=True, padx=4, pady=5, side="left")
        y.pack(side="right", fill="y")
        x.pack(side="bottom", fill="x")

    def _build_priority_tab(self):
        cols = ("rank", "district", "SCI", "openings", "VOI", "confidence", "gap", "needs", "basis")
        self.priority_tree = ttk.Treeview(self.tab_priority, columns=cols, show="headings")
        labels = {"rank":"Rank","district":"District","SCI":"SCI","openings":"Annual openings","VOI":"VOI","confidence":"Confidence","gap":"Gap cells","needs":"Needs data","basis":"Supply basis"}
        for c in cols:
            self.priority_tree.heading(c, text=labels[c])
            self.priority_tree.column(c, width=130 if c!="district" else 180)
        self.priority_tree.pack(fill="both", expand=True, padx=5, pady=5)
        note = tk.Label(
            self.tab_priority,
            text="VOI = interval width × annual openings. Higher VOI means KSISU gets more value from collecting better district data there first.",
            anchor="w", justify="left", bg="#f4f7fb", fg="#31455f"
        )
        note.pack(fill="x", padx=5, pady=(0,5))

    def _build_sensitivity_tab(self):
        self.sensitivity_text = tk.Text(self.tab_sensitivity, wrap="word", height=14)
        self.sensitivity_text.pack(fill="x", padx=5, pady=5)
        cols = ("district","parameter","base","low","high","effect")
        self.sensitivity_tree = ttk.Treeview(self.tab_sensitivity, columns=cols, show="headings")
        for c, label in [("district","District"),("parameter","Parameter"),("base","Base ratio"),("low","Low"),("high","High"),("effect","Absolute effect")]:
            self.sensitivity_tree.heading(c, text=label)
            self.sensitivity_tree.column(c, width=160 if c in ["district","parameter"] else 120)
        self.sensitivity_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_validation_tab(self):
        self.validation_text = tk.Text(self.tab_validation, wrap="word", height=12)
        self.validation_text.pack(fill="x", padx=5, pady=5)
        ttk.Label(self.tab_validation, text="Corruption test and source readiness", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=5)
        cols=("metric","value","status")
        self.validation_tree=ttk.Treeview(self.tab_validation,columns=cols,show="headings")
        for c,l in [("metric","Metric"),("value","Value"),("status","Status")]:
            self.validation_tree.heading(c,text=l); self.validation_tree.column(c,width=250)
        self.validation_tree.pack(fill="both",expand=True,padx=5,pady=5)

    def _build_demo_tab(self):
        txt = tk.Text(self.tab_demo, wrap="word", font=("Segoe UI", 10), bg="#ffffff")
        txt.pack(fill="both", expand=True, padx=5, pady=5)
        demo = '''HOW TO DEMONSTRATE THIS TO THE JUDGES\n\n1. Start on Inputs & Assumptions. Say: "We are not assuming every district has clean data. I can replace any source file and rerun the same evidence chain."\n\n2. Click Run Analysis. Show the result table. The model uses 2022-23 public data and the requested manufacturing trades only: NCO 72, 74 and 81. Every result has a year, source basis, interval and confidence.\n\n3. Open District Priority. Say: "I do not ask the government to trust a red/green dashboard. I ask where better district data would change the decision most." Show SCI and VOI ranking.\n\n4. Load Actual District Supply. Use a CSV exported from NCVT MIS / a Karnataka ITI source with district + trade seats. Enter the real seats for Tumakuru and Kalaburagi. Click Run Analysis again.\n\n5. Compare the same districts. The rows switch from district-proxy to district-actual. The seat uncertainty narrows, so the ratio interval should narrow. This is the live proof of the "interval shrinks when district data arrives" claim.\n\n6. Open Sensitivity. Show the top parameter driving the ratio. Say: "We know which assumption matters, so KSISU knows what to collect next."\n\n7. Open Validation & Linkage. Show the corruption test: Bangalore/Bengaluru, Gulbarga/Kalaburagi, typos and duplicates. Then show the recovery rate.\n\n8. Final line: "The product is not the dashboard. The product is a reproducible evidence pipeline that tells KSISU what it can infer today, what remains uncertain, and which district data to request first."\n\nLIVE INPUT FILE FORMAT\nDistrict actual supply CSV columns:\n- district\n- nco_group_2digit OR trade\n- seats\n\nExample:\nTumakuru,72,1250,Fitter\nTumakuru,74,900,Electrician\nKalaburagi,72,700,Fitter\n\nDo not type made-up values into the competition demo. Use values from the NCVT MIS / DGT / Karnataka source you have downloaded.\n'''
        txt.insert("1.0", demo)
        txt.configure(state="disabled")

    def _populate_source_tree(self):
        grains={"lgd":"district","employment":"district","asi":"state","ncvt":"state","occupation_mix":"state prior","crosswalk":"course→NCO","dgt":"division","division_map":"district→division"}
        for item in self.source_tree.get_children(): self.source_tree.delete(item)
        for k,p in self.paths.items():
            self.source_tree.insert("", "end", iid=k, values=(k, p, grains.get(k, "")))

    def change_source(self):
        selected = self.source_tree.selection()
        if not selected: return
        key=selected[0]
        path=filedialog.askopenfilename(title=f"Choose {key} file", filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if path:
            self.paths[key]=path
            self._populate_source_tree()
            self.status.set(f"Updated {key} source: {path}")

    def load_actual_supply(self):
        path=filedialog.askopenfilename(title="Select district ITI supply CSV", filetypes=[("CSV files","*.csv")])
        if path:
            self.actual_supply.set(path)
            self.status.set("District-actual supply loaded. Run Analysis to compare proxy vs actual.")

    def manual_supply_entry(self):
        win=tk.Toplevel(self)
        win.title("Manual district-actual ITI supply")
        win.geometry("700x420")
        win.transient(self); win.grab_set()
        ttk.Label(win, text="Enter seats from your real NCVT MIS / DGT / Karnataka extract. This writes a temporary CSV for the model.", wraplength=650).pack(anchor="w", padx=12, pady=10)
        cols=("district","group","trade","seats")
        tree=ttk.Treeview(win, columns=cols, show="headings", height=9)
        for c,w in [("district",150),("group",80),("trade",260),("seats",100)]:
            tree.heading(c,text=c.title()); tree.column(c,width=w)
        tree.pack(fill="both",expand=True,padx=12,pady=8)
        rows=[
            ("Tumakuru","72","Fitter",""),("Tumakuru","74","Electrician",""),("Tumakuru","81","CNC Milling Machine Operator",""),
            ("Kalaburagi","72","Fitter",""),("Kalaburagi","74","Electrician",""),("Kalaburagi","81","CNC Milling Machine Operator","")
        ]
        entries=[]
        for row in rows:
            iid=tree.insert("","end",values=row)
            entries.append(iid)
        def edit(event):
            region=tree.identify("region",event.x,event.y)
            if region != "cell": return
            iid=tree.identify_row(event.y); col=tree.identify_column(event.x)
            if col != "#4": return
            x,y,w,h=tree.bbox(iid,col)
            e=ttk.Entry(tree,width=10); e.place(x=x,y=y,width=w,height=h)
            e.insert(0,tree.set(iid,"seats")); e.focus_set()
            def done(_=None):
                tree.set(iid,"seats",e.get()); e.destroy()
            e.bind("<Return>",done); e.bind("<FocusOut>",done)
        tree.bind("<Double-1>",edit)
        def save():
            rows_out=[]
            for iid in entries:
                vals=tree.item(iid,"values")
                try: seats=float(vals[3])
                except Exception:
                    messagebox.showerror("Missing seats","Double-click the Seats cell and enter a real seat count for every row.",parent=win); return
                rows_out.append({"district":vals[0],"nco_group_2digit":vals[1],"trade":vals[2],"seats":seats})
            path=ROOT/"out"/"district_iti_supply.csv"
            pd.DataFrame(rows_out).to_csv(path,index=False)
            self.actual_supply.set(str(path))
            self.status.set("Manual district-actual supply saved to out/district_iti_supply.csv")
            win.destroy()
        ttk.Button(win,text="Save and use in model",command=save).pack(side="right",padx=12,pady=10)
        ttk.Button(win,text="Cancel",command=win.destroy).pack(side="right",pady=10)

    def clear_actual_supply(self):
        self.actual_supply.set("")
        self.status.set("District-actual supply cleared. The model will use the proxy layer.")

    def open_output(self):
        try:
            os.startfile(str(OUT))
        except Exception:
            subprocess.Popen([sys.executable, "-c", "import os; print(os.path.abspath('out'))"], cwd=ROOT)

    def open_readme(self):
        p=ROOT/"README.md"
        try:
            os.startfile(str(p))
        except Exception:
            messagebox.showinfo("README", p.read_text(encoding="utf-8"))

    def _get_float(self, var, label):
        try: return float(var.get())
        except Exception: raise ValueError(f"{label} must be numeric")

    def _collect_overrides(self):
        groups=[g for g,v in self.selected_groups.items() if v.get()]
        if not groups: raise ValueError("Select at least one NCO group.")
        return {
            "selected_nco_groups": groups,
            "monte_carlo_draws": int(self.draws_var.get()),
            "random_seed": int(self.seed_var.get()),
            "opening_rate": {"low":self._get_float(self.open_low,'opening low'),"mode":self._get_float(self.open_mode,'opening mode'),"high":self._get_float(self.open_high,'opening high')},
            "seat_fill_rate": {"low":self._get_float(self.fill_low,'fill low'),"mode":self._get_float(self.fill_mode,'fill mode'),"high":self._get_float(self.fill_high,'fill high')},
            "completion_rate": {"low":self._get_float(self.comp_low,'completion low'),"mode":self._get_float(self.comp_mode,'completion mode'),"high":self._get_float(self.comp_high,'completion high')},
            "sector_entry_rate": {"low":self._get_float(self.entry_low,'entry low'),"mode":self._get_float(self.entry_mode,'entry mode'),"high":self._get_float(self.entry_high,'entry high')},
        }

    def run_analysis(self):
        try:
            overrides=self._collect_overrides()
            self.status.set("Running evidence pipeline...")
            self.update_idletasks()
            res=compute_model(self.paths, overrides=overrides, actual_supply_path=(self.actual_supply.get() or None))
            if not self.actual_supply.get():
                self._baseline_ratio = res["ratio"].copy()
            self._last_results=res
            self._render_results(res)
            self._render_priority(res)
            self._render_sensitivity(res)
            self._render_validation(res)
            counts=res["ratio"]["signal"].value_counts().to_dict()
            decision_counts=res["ratio"]["decision_status"].value_counts().to_dict()
            self.result_summary.set(f"{len(res['district'])} districts • {len(res['ratio'])} district×occupation rows • {decision_counts.get('PROVISIONAL GAP',0)} provisional gaps • {decision_counts.get('NEEDS DATA',0)} need data")
            self.status.set("Run complete. Every output is written to out/ with source lineage and assumptions.")
            self.nb.select(self.tab_results)
        except Exception as e:
            self.status.set("Run failed")
            messagebox.showerror("Model error", str(e))

    def _render_results(self,res):
        for i in self.results_tree.get_children(): self.results_tree.delete(i)
        df=res["ratio"].copy()
        for _,r in df.iterrows():
            self.results_tree.insert("", "end", values=(r.district,r.nco_group_2digit,r.occupation_label,f"{r.ratio_p10:.2f}",f"{r.ratio_median:.2f}",f"{r.ratio_p90:.2f}",f"{r.interval_width:.2f}",f"{100*r.confidence_score:.0f}%",r.decision_status,r.supply_basis))

    def _render_priority(self,res):
        for i in self.priority_tree.get_children(): self.priority_tree.delete(i)
        df=res["district"].copy()
        for _,r in df.iterrows():
            self.priority_tree.insert("", "end", values=(int(r.priority_rank),r.district,f"{r.SCI:.3f}",f"{r.total_annual_openings:,.0f}",f"{r.VOI:,.0f}",f"{100*r.mean_confidence:.0f}%",int(r.gap_cells),int(r.needs_data_cells),r.supply_basis))

    def _render_sensitivity(self,res):
        self.sensitivity_text.delete("1.0","end")
        s=res["sensitivity"].copy()
        top=s.groupby("parameter")["absolute_effect"].mean().sort_values(ascending=False)
        lines=["Sensitivity: one-parameter-at-a-time movement around the central scenario.","", "Largest driver(s):"]+[f"- {p}: mean absolute ratio effect {v:.3f}" for p,v in top.items()]
        self.sensitivity_text.insert("1.0","\n".join(lines))
        for i in self.sensitivity_tree.get_children(): self.sensitivity_tree.delete(i)
        for _,r in s.head(40).iterrows():
            self.sensitivity_tree.insert("", "end", values=(r.district,r.parameter,f"{r.base_ratio:.3f}",f"{r.low_ratio:.3f}",f"{r.high_ratio:.3f}",f"{r.absolute_effect:.3f}"))

    def _render_validation(self,res):
        self.validation_text.delete("1.0","end")
        c=res["corruption"].iloc[0]
        san=res["sanity"].iloc[0]
        lines=[
            f"Corruption test: recovered {int(c.matched_unique_districts)} of {int(c.clean_districts)} districts ({100*c.matching_recovery_rate:.1f}%), removed {int(c.duplicates_removed)} duplicate rows.",
            f"Sanity check: {san['check']}; median absolute share difference = {float(san['median_abs_share_diff_pct_points']):.2f} percentage points.",
            f"Note: {san['note']}",
        ]
        if self._baseline_ratio is not None and (res["ratio"]["evidence_ready"].any()):
            b=self._baseline_ratio[["district","nco_group_2digit","interval_width"]].rename(columns={"interval_width":"proxy_width"})
            a=res["ratio"][["district","nco_group_2digit","interval_width","supply_basis"]]
            m=b.merge(a,on=["district","nco_group_2digit"],how="inner")
            m["shrink_pct"]=(m.proxy_width-m.interval_width)/m.proxy_width*100
            focus=m[m.district.isin(["Tumakuru","Kalaburagi"])].copy()
            if not focus.empty:
                lines.append("Interval-shrink demonstration (after district-actual supply):")
                for _,rr in focus.head(6).iterrows():
                    lines.append(f"- {rr.district} NCO {rr.nco_group_2digit}: width {rr.proxy_width:.3f} -> {rr.interval_width:.3f} ({rr.shrink_pct:.1f}% narrower)")
        lines += ["", "Source policy: public/aggregated only. Unmatched rows remain visible and can be sent to human review."]
        self.validation_text.insert("1.0","\n".join(lines))
        for i in self.validation_tree.get_children(): self.validation_tree.delete(i)
        self.validation_tree.insert("","end",values=("District matching recovery",f"{100*c.matching_recovery_rate:.1f}%", "PASS" if c.status=='PASS' else 'REVIEW'))
        self.validation_tree.insert("","end",values=("Duplicates removed in corruption test",int(c.duplicates_removed),"PASS"))
        self.validation_tree.insert("","end",values=("Median proxy-share change",f"{float(san['median_abs_share_diff_pct_points']):.2f} pp","CHECK"))


if __name__ == "__main__":
    app=KSISUGUI()
    app.mainloop()
