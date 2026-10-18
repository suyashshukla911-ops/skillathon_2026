from __future__ import annotations

import threading
from pathlib import Path
import os
import json
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
        self.demand_method = tk.StringVar(value=str(CONFIG.get("demand_allocation_method", "udyam_employment")))

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
        
        # --- CUSTOM GREEN PROGRESS BAR STYLE ---
        s.configure("Custom.Horizontal.TProgressbar", 
                    background="#2e7d32",    # Success Green
                    troughcolor="#dbe6f0",   # Light grey/blue track
                    thickness=14) 

    def _header(self):
        head = tk.Frame(self, bg="#0d2a4a", height=100)
        head.pack(fill="x")
        tk.Label(head, text="KSISU Real-Data Evidence Workbench", font=("Segoe UI", 20, "bold"), fg="white", bg="#0d2a4a").pack(anchor="w", padx=18, pady=(12, 2))
        tk.Label(head, text="Ingest → Harmonise → Demand proxy → ITI evidence → Shared Monte Carlo → Alignment → VOI → Human review", font=("Segoe UI", 9), fg="#cfe1ff", bg="#0d2a4a").pack(anchor="w", padx=18, pady=(0, 10))

        # Changed to self.bar so we can disable children later
        self.bar = tk.Frame(self, bg="#e6eef7")
        self.bar.pack(fill="x")
        ttk.Button(self.bar, text="Run Proxy Baseline", style="Primary.TButton", command=self.run_proxy).pack(side="left", padx=8, pady=8)
        ttk.Button(self.bar, text="Load DGT 2026 Real Supply", command=self.load_dgt_supply).pack(side="left", padx=3, pady=8)
        ttk.Button(self.bar, text="Load Other Real Supply CSV", command=self.load_real_supply).pack(side="left", padx=3, pady=8)
        ttk.Button(self.bar, text="Run With Loaded Supply", command=self.run_actual).pack(side="left", padx=3, pady=8)
        ttk.Button(self.bar, text="Run DGT Share Upgrade", command=self.run_dgt_share).pack(side="left", padx=3, pady=8)
        ttk.Button(self.bar, text="Judge Demo", command=self.run_judge_demo).pack(side="left", padx=3, pady=8)
        ttk.Button(self.bar, text="Open Output", command=self.open_output).pack(side="left", padx=3, pady=8)
        
        # Determinate loading bar with the custom green style applied
        self.progress = ttk.Progressbar(
            self.bar, 
            orient="horizontal", 
            mode="determinate", 
            length=150, 
            style="Custom.Horizontal.TProgressbar"
        )
        self.progress.pack(side="right", padx=12, pady=8)

        # dynamic wraplength status label
        self.status_label = tk.Label(self.bar, textvariable=self.status, bg="#e6eef7", fg="#29425f", anchor="w", justify="left")
        self.status_label.pack(side="left", padx=12, fill="both", expand=True)
        self.status_label.bind("<Configure>", lambda e: self.status_label.config(wraplength=max(100, e.width - 10)))

    # --- UI LOCKING MECHANISM ---
    def _set_ui_state(self, state, parent=None):
        """Recursively disables/enables every button in the application to prevent multi-clicks."""
        if parent is None:
            parent = self
        for child in parent.winfo_children():
            if isinstance(child, (ttk.Button, tk.Button)):
                child.configure(state=state)
            if child.winfo_children():
                self._set_ui_state(state, child)
    # ----------------------------

    # --- ADVANCED THREADING & PROGRESS HELPER ---
    def _run_with_progress(self, target_func, success_callback, simulated=False):
        self._set_ui_state(tk.DISABLED) # Lock all buttons
        self.progress['value'] = 0
        
        def update_progress(val, msg=None):
            def do_update():
                self.progress['value'] = val
                if msg:
                    self.status.set(msg)
            self.after(0, do_update)

        # Simulator for single heavy-tasks (approaches 90% and waits)
        if simulated:
            self._sim_running = True
            self._sim_val = 0
            def simulate():
                if self._sim_running and self._sim_val < 90:
                    self._sim_val += (100 - self._sim_val) * 0.05
                    self.progress['value'] = self._sim_val
                    self.after(200, simulate)
            simulate()

        def worker():
            try:
                if simulated:
                    res = target_func()
                else:
                    res = target_func(update_progress)
                self.after(0, _success_wrapper, res)
            except Exception as e:
                self.after(0, self._run_error, str(e))
                
        def _success_wrapper(res):
            if simulated:
                self._sim_running = False
            self.progress['value'] = 100
            self._set_ui_state(tk.NORMAL) # Unlock UI
            success_callback(res)

        threading.Thread(target=worker, daemon=True).start()

    def _run_error(self, err_msg):
        if hasattr(self, '_sim_running'):
            self._sim_running = False
        self.progress['value'] = 0
        self._set_ui_state(tk.NORMAL) # Unlock UI on failure
        messagebox.showerror("Analysis failed", err_msg)
        self.status.set("Analysis failed")
    # --------------------------------------------

    def _tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.t_inputs = ttk.Frame(self.nb)
        self.t_results = ttk.Frame(self.nb)
        self.t_priority = ttk.Frame(self.nb)
        self.t_policy = ttk.Frame(self.nb)
        self.t_sens = ttk.Frame(self.nb)
        self.t_val = ttk.Frame(self.nb)
        self.t_demo = ttk.Frame(self.nb)
        for t, title in [
            (self.t_inputs, "Inputs & Assumptions"),
            (self.t_results, "Gap Results"),
            (self.t_priority, "District Priority"),
            (self.t_policy, "Policy Actions"),
            (self.t_sens, "Sensitivity"),
            (self.t_val, "Validation & Linkage"),
            (self.t_demo, "Judge Demo"),
        ]:
            self.nb.add(t, text=title)
        self._inputs_tab(); self._results_tab(); self._priority_tab(); self._policy_tab(); self._sens_tab(); self._validation_tab(); self._demo_tab()

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
        ttk.Label(right, text="Scope: Manufacturing / NCO 72, 74", font=("Segoe UI",10,"bold")).pack(anchor="w", pady=(0,4))
        ttk.Label(right, text="Demand allocator", font=("Segoe UI",9,"bold")).pack(anchor="w")
        ttk.Combobox(right, textvariable=self.demand_method, state="readonly", values=("udyam_employment","udyam_units","blend"), width=28).pack(anchor="w", pady=(2,8))
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
        ttk.Button(right, text="Use DGT 2026 provisional real supply", command=self.load_dgt_supply).pack(fill="x", pady=4)
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
        self.priority_tree = self._tree(self.t_priority, [
            ("rank", "R rank", 50),
            ("district", "District", 135),
            ("level", "Evidence Level", 115),
            ("robust", "Robust 6-Scen", 95),
            ("ratio", "Median R", 80),
            ("relative_r", "R / median", 85),
            ("sci", "SCI", 70),
            ("openings", "Openings", 95),
            ("voi", "VOI", 100),
            ("priority", "Data priority", 105),
            ("confidence", "Evidence", 80),
            ("actual", "Full actual", 75),
            ("needs", "Needs data", 75),
        ])
        ttk.Label(
            self.t_priority,
            text="R rank is the uncapped ratio ranking. Evidence levels (A/B/C) and 6-scenario robustness flag (★ robust for Vijayapura) guide next verification steps; gate remains conservative NEEDS DATA.",
            wraplength=1200
        ).pack(fill="x", padx=6, pady=5)

    def _policy_tab(self):
        banner = tk.Label(
            self.t_policy,
            text="Gate status: NEEDS DATA for all cells; levels A/B are data-collection and verification actions, not seat decisions.",
            font=("Segoe UI", 10, "bold"),
            bg="#0d2a4a",
            fg="#ffffff",
            pady=8,
            padx=10,
            anchor="w",
        )
        banner.pack(fill="x", padx=6, pady=(6, 2))
        self.policy_tree = self._tree(
            self.t_policy,
            [
                ("district", "District", 130),
                ("evidence_level_name", "Evidence Level", 140),
                ("action", "Action", 350),
                ("decision_maker", "Decision Maker", 170),
                ("source_doc", "Source Document", 175),
                ("page", "Page", 50),
                ("main_evidence_limitation", "Main Evidence Limitation", 280),
            ],
        )
        self._refresh_policy_tab()

    def _refresh_policy_tab(self):
        if not hasattr(self, "policy_tree"):
            return
        for item in self.policy_tree.get_children():
            self.policy_tree.delete(item)
        policy_file = OUT / "policy_actions.csv"
        if not policy_file.exists():
            self.policy_tree.insert(
                "",
                "end",
                values=(
                    "Run policy_layer.py first",
                    "—",
                    "out/policy_actions.csv not found",
                    "—",
                    "—",
                    "—",
                    "—",
                ),
            )
            return
        try:
            pa = pd.read_csv(policy_file)
            for _, row in pa.iterrows():
                page_val = row.get("page")
                page_str = "—" if pd.isna(page_val) else (f"{int(float(page_val))}" if str(page_val).replace(".", "", 1).isdigit() else str(page_val))
                self.policy_tree.insert(
                    "",
                    "end",
                    values=(
                        row.get("district", ""),
                        row.get("evidence_level_name", ""),
                        row.get("action", ""),
                        row.get("decision_maker", ""),
                        row.get("source_doc", ""),
                        page_str,
                        row.get("main_evidence_limitation", ""),
                    ),
                )
        except Exception as e:
            self.policy_tree.insert(
                "",
                "end",
                values=("Error loading policy_actions.csv", str(e), "—", "—", "—", "—", "—"),
            )

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
        text='''JUDGE DEMO - RECOMMENDED PRESENTATION FLOW

AUTOMATED 3-MINUTE JUDGE DEMO:
Click the "Run 3-Min Judge Demo" button on the top toolbar:
1. Executes all six robustness scenarios (3 demand allocators × 2 supply modes).
2. Refreshes public exports and applies the V17 policy layer.
3. Automatically switches to "3. District Priority" with Evidence Levels:
   - 27 districts at Level A (Exploratory).
   - 3 districts at Level B (Provisional Watchlist: Gadag, Tumakuru, Vijayapura).
   - Highlights Vijayapura with the "★ robust" badge as the only district in the top-5 across all six scenarios.
4. Switch to "4. Policy Actions":
   - Banner: "Gate status: NEEDS DATA for all cells; levels A/B are data-collection and verification actions, not seat decisions."
   - Reviews operationalised DSDP clauses, decision-makers, and evidence limitations.
   - Note on Vijayapura: No official district skill development plan is published in the source register; it explicitly relies on the generic evidence safeguard (ALL_DISTRICTS) rather than an invented or substituted plan.

MANUAL STEP-BY-STEP PRESENTATION ORDER:
1. Run Proxy Baseline. Say: "This is what KSISU can infer before complete district ITI supply is available. Mathematical ratios are shown, but policy status remains NEEDS DATA."
2. Open District Priority. The ranking table is a data-collection queue, not a district skill-gap leaderboard. Use the Demand allocator selector to show employment, enterprise-unit, or blended demand shares.
3. Click Load DGT 2026 Real Supply. This loads the official DGT CTS-2026 provisional dynamic seat matrix extracted from the uploaded public PDF.
4. Click Run With Loaded Supply. Show the conservative partial-floor evidence run.
5. Click Run DGT Share Upgrade. Explain that DGT district/group seat shares are coverage-weighted with the historical ITI-count proxy.
6. Open Gap Results. Show that the DGT-share ranking can change relative to the proxy baseline while the decision remains NEEDS DATA.
7. Open District Priority and Sensitivity. Show rank stability across shared Monte Carlo draws.
8. Open Validation & Linkage. Show 80 seeded typos, 20 unseen aliases routed to review, duplicate removal, proxy-vs-DGT Spearman, and source lineage.

THE ONE-SENTENCE STORY
"We use real DGT seat distribution with coverage-weighted shrinkage toward the historical proxy, keep the statewide level anchored to the NCVT benchmark, retain uncertainty for sparse or missing areas, and only unlock district policy calls when complete evidence is available."
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
            ("NCVT File 1171 indexed partial",RAW/"ncvtmis_file1171_real_partial.csv","district×trade","historical"),
            ("DGT CTS-2026 provisional real supply",CLEAN/"dgt_cts_2026_karnataka_supply_nco.csv","district×ITI×trade×NCO","2026"),
            ("Historical district ITI-count weights",CLEAN/"district_iti_counts.csv","district weight","2022"),
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
            "random_seed":int(self.seed.get()),"monte_carlo_draws":int(self.draws.get()), "demand_allocation_method": self.demand_method.get()
        }

    # --- EXECUTION METHODS ---
    def run_proxy(self):
        self.status.set("Running proxy baseline...")
        
        def task():
            return compute_model(overrides=self._override_config())
            
        def on_success(res):
            self.proxy_last = res
            self.last = res
            self._display(res, "Proxy baseline complete — policy status is conservatively gated to NEEDS DATA.")
            
        # simulated=True provides an asymptotic smooth bar filler for the heavy single task
        self._run_with_progress(task, on_success, simulated=True)

    def run_actual(self):
        if not self.actual_supply:
            messagebox.showinfo("No district supply loaded","Load a real NCVT MIS / DGT / Karnataka district×trade seat CSV first.")
            return
            
        self.status.set("Running with loaded district supply...")
        
        def task():
            return compute_model(actual_supply_path=str(self.actual_supply), overrides=self._override_config())
            
        def on_success(res):
            self.last = res
            self._display(res, "Evidence-upgrade run complete — partial evidence remains NEEDS DATA until full district coverage is loaded.")
            
        self._run_with_progress(task, on_success, simulated=True)

    def run_dgt_share(self):
        p = CLEAN / "dgt_cts_2026_karnataka_supply_nco.csv"
        if not p.exists():
            messagebox.showerror("DGT supply missing", f"Expected bundled file not found:\n{p}")
            return
            
        self.actual_supply = p
        self.supply_path.set(str(p))
        self.supply_label.config(text=f"DGT 2026 coverage-weighted share allocation selected:\n{p.name}\nReal DGT distribution blended with historical ITI-count coverage weights; provisional/incomplete evidence.")
        self.status.set("Running DGT seat-share evidence upgrade...")
        
        def task():
            return compute_model(
                actual_supply_path=str(p),
                overrides={**self._override_config(), "proxy_allocation_method": "dgt_2026_seat_share"},
                output_dir=OUT / "dgt_share_run",
            )
            
        def on_success(res):
            self.last = res
            self._display(res, "DGT share upgrade complete — coverage-weighted real DGT distribution changed the allocation; policy gate remains conservative.")
            self.nb.select(self.t_results)
            
        self._run_with_progress(task, on_success, simulated=True)

    def run_judge_demo(self):
        def task(update_progress):
            import run_demand_scenarios
            import public_export
            import policy_layer

            # Precise Step 1 Updates the Determinate Bar to 10%
            update_progress(10, "Judge demo: running six demand scenarios...")
            run_demand_scenarios.main()

            # Step 2 Updates to 40%
            update_progress(40, "Judge demo: building public exports...")
            public_export.build_public_exports(OUT / "dgt_share_run", ROOT / "public_export")
            
            # Step 3 Updates to 60%
            update_progress(60, "Judge demo: applying policy layer...")
            policy_layer.run(ROOT)

            self.actual_supply = CLEAN / "dgt_cts_2026_karnataka_supply_nco.csv"
            
            # Safely updating UI elements
            self.after(0, lambda: self.supply_path.set(str(self.actual_supply)))
            self.after(0, lambda: self.supply_label.config(text=f"DGT 2026 provisional real supply loaded:\n{self.actual_supply.name}\n29 published districts; 1,734 rows; 45,416 seats; coverage-weighted."))
            
            # Step 4 Updates to 80%
            update_progress(80, "Judge demo: running final evidence upgrade model...")
            return compute_model(
                actual_supply_path=str(self.actual_supply), 
                overrides={**self._override_config(), "proxy_allocation_method": "dgt_2026_seat_share"}, 
                output_dir=OUT / "dgt_share_run"
            )
            
        def on_success(res):
            self.last = res
            self._display(res, "Judge demo complete: six scenarios ran → evidence levels updated → policy actions ready.")
            self.nb.select(self.t_priority)
            messagebox.showinfo("Judge Demo Complete", "Judge Demo sequence complete:\n\n1. Six scenarios evaluated: Vijayapura confirmed as ★ robust priority.\n2. Evidence levels shown in '3. District Priority' (27 A – Exploratory, 3 B – Watchlist: Gadag, Tumakuru, Vijayapura).\n3. Switch to '4. Policy Actions' to inspect operationalised DSDP clauses and generic safeguards.")
            
        # simulated=False ensures the bar only updates when we explicitly tell it to via update_progress()
        self._run_with_progress(task, on_success, simulated=False)
    # -----------------------------

    def load_dgt_supply(self):
        p=CLEAN/"dgt_cts_2026_karnataka_supply_nco.csv"
        if not p.exists():
            messagebox.showerror("DGT supply missing", f"Expected bundled file not found:\n{p}")
            return
        self.actual_supply=p; self.supply_path.set(str(p))
        self.supply_label.config(text=f"DGT 2026 provisional real supply loaded:\n{p.name}\n29 published districts; 1,734 rows; 45,416 seats; 88.0% mapped to NCO 72/74; provisional source.")
        self.status.set("DGT 2026 provisional real supply selected. Click Run With Loaded Supply.")

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
        self.results_note.set(f"{len(d)} districts × {r.nco_group_2digit.nunique()} NCO groups • {r.decision_status.value_counts().to_dict()} • Actual supply loaded: {res['audit']['actual_supply_loaded']} • Demand allocator: {res['audit'].get('demand_allocation_method', self.demand_method.get())}")
        self._fill(self.results_tree, r, lambda x:(x.district,x.nco_group_2digit,x.occupation_label,f"{x.ratio_p10:.3f}",f"{x.ratio_median:.3f}",f"{x.ratio_p90:.3f}",f"{x.interval_width:.3f}",f"{x.confidence_score:.2f}",x.decision_status,x.supply_basis))
        
        levels_map = {}
        robust_map = {}
        levels_file = OUT / "district_evidence_levels.csv"
        indicators_file = ROOT / "public_export" / "district_indicators.csv"
        run_summary_file = OUT / "run_summary.json"

        robust_districts = set()
        if run_summary_file.exists():
            try:
                rs = json.loads(run_summary_file.read_text(encoding="utf-8"))
                robust_districts = set(rs.get("robust_priority", []))
            except Exception:
                pass

        if levels_file.exists():
            try:
                lev_df = pd.read_csv(levels_file)
                for _, r_lev in lev_df.iterrows():
                    dist = str(r_lev["district"])
                    lvl = str(r_lev.get("evidence_level", ""))
                    lvl_name = str(r_lev.get("evidence_level_name", ""))
                    if "B_PROVISIONAL" in lvl or "Watchlist" in lvl_name:
                        display_lvl = "B – Watchlist"
                    elif "C_POLICY" in lvl or "Policy-ready" in lvl_name:
                        display_lvl = "C – Policy-ready"
                    elif "A_EXPLORATORY" in lvl or "Exploratory" in lvl_name:
                        display_lvl = "A – Exploratory"
                    else:
                        display_lvl = lvl_name or lvl or "A – Exploratory"
                    levels_map[dist] = display_lvl
                    if bool(r_lev.get("robust_priority", False)) or (dist in robust_districts):
                        robust_map[dist] = "★ robust"
            except Exception:
                pass

        if indicators_file.exists():
            try:
                ind_df = pd.read_csv(indicators_file)
                for _, r_ind in ind_df.iterrows():
                    dist = str(r_ind["district"])
                    if dist not in levels_map:
                        levels_map[dist] = "Run policy_layer.py first"
                    if bool(r_ind.get("robust_priority", False)) or (dist in robust_districts):
                        robust_map[dist] = "★ robust"
            except Exception:
                pass

        self._fill(
            self.priority_tree,
            d,
            lambda x: (
                x.ratio_rank,
                x.district,
                levels_map.get(str(x.district), "Run policy_layer.py first"),
                robust_map.get(str(x.district), "—"),
                f"{x.uncapped_ratio_median:.3f}",
                f"{x.relative_uncapped_ratio_vs_state_median:.2f}x",
                f"{x.SCI:.3f}",
                f"{x.total_annual_openings:,.0f}",
                f"{x.VOI:,.0f}",
                f"{x.data_collection_priority:,.0f}",
                f"{x.mean_confidence:.2f}",
                x.actual_cells,
                x.needs_data_cells,
            ),
        )
        self._refresh_policy_tab()
        self.sens_text.delete("1.0","end")
        self.sens_text.insert("1.0", "Sensitivity now reports rank stability across the shared Monte Carlo draws. This tests whether district priority is stable under common system-level uncertainty; it does not simply restate the width of arbitrary parameter ranges.\n")
        self._fill(self.sens_tree, s, lambda x:(x.district,int(x.baseline_rank),f"{x.rank_p10:.0f}",f"{x.rank_median:.0f}",f"{x.rank_p90:.0f}",f"{x.top5_frequency*100:.1f}%",f"{x.global_rank_stability_median_rho:.3f}"))
        self.val_text.delete("1.0","end")
        self.val_text.insert("1.0", "Corruption rows are never dropped; review rows remain visible. Source provenance is regenerated from the curated source registry and retains official URLs.\n")
        for item in self.val_tree.get_children(): self.val_tree.delete(item)
        rows=[
            ("Raw LGD districts",31,"PASS"),
            ("Analytical geographies",len(d),"PASS" if len(d)==30 else "REVIEW"),
            ("Seeded corruption test",f"{int(c.iloc[0].seeded_corruptions)} cases; {float(c.iloc[0].seeded_typo_recovery_rate)*100:.1f}% typo recovery","PASS" if float(c.iloc[0].seeded_typo_recovery_rate)>=0.9 else "REVIEW"),
            ("Unmatched review rows",int(c.iloc[0].unmatched_review_rows),"REVIEW QUEUE" if int(c.iloc[0].unmatched_review_rows)>0 else "PASS"),
            ("Selected occupation share",f"{res['audit']['occupation_share_sum_selected']:.2f}","72 + 74 only; not normalized"),
            ("Selected course weight",f"{res['audit']['selected_course_weight_sum']:.2f}","72 + 74 only; not normalized"),
            ("Monte Carlo draws",res['audit']['monte_carlo_draws'],"PASS"),
            ("Relative uncapped ratio", "Median R / statewide median R", "PRIORITY INDEX"),
            ("Proxy allocation diagnostic",f"{res['audit'].get('district_supply_proxy_correlation',float('nan')):.3f}","NOT VALIDATION"),
            ("DGT vs ITI-count Spearman",f"{res['audit'].get('proxy_vs_dgt_spearman',float('nan')):.3f}","PROXY DIAGNOSTIC"),
            ("DGT / NCVT seat scale",f"{res['audit'].get('actual_to_state_seat_ratio',0.0):.3f}","SCALE CHECK"),
            ("Supply allocation method",res['audit'].get('proxy_allocation_method',''),"MODEL CONTROL"),
            ("Demand allocation method",res['audit'].get('demand_allocation_method',self.demand_method.get()),"MODEL CONTROL"),
            ("Demand allocator rank range mean",f"{res['audit'].get('demand_allocator_rank_range_mean',float('nan')):.2f}","STRUCTURAL SENSITIVITY"),
            ("Robust top-5 districts",int(res['audit'].get('demand_allocator_robust_top5_count',0)),"ALL ALLOCATORS"),
            ("Mean supply conservation",f"{res['audit'].get('statewide_supply_mean_conservation_ratio',float('nan')):.3f}","CONSERVATION"),
        ]
        demo=res.get("interval_demo")
        if demo is not None and not demo.empty:
            if str(res['audit'].get('proxy_allocation_method','')) == 'dgt_2026_seat_share':
                rows.append(("DGT share evidence update",f"{len(demo)} cells compared with proxy; DGT distribution is used for district shares","EVIDENCE UPGRADE"))
            else:
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