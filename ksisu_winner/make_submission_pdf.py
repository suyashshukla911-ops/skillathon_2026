from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage, KeepTogether
from reportlab.lib.units import mm

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'out'
CLEAN = ROOT / 'clean'
RAW = ROOT / 'raw'
SHOT = ROOT / 'judge_screenshots' / 'pdf_use'
OUT.mkdir(exist_ok=True)

BLUE = colors.HexColor('#0D2A4A')
LIGHT = colors.HexColor('#EEF3F9')
MID = colors.HexColor('#D7E1EC')
GREEN = colors.HexColor('#1D7A46')
AMBER = colors.HexColor('#8A6200')
RED = colors.HexColor('#A32C2C')
WHITE = colors.white

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='Title2', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=25, leading=29, textColor=BLUE, spaceAfter=8))
styles.add(ParagraphStyle(name='H2b', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=16, leading=19, textColor=BLUE, spaceAfter=6))
styles.add(ParagraphStyle(name='Body2x', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.8, leading=11.0, textColor=colors.HexColor('#24364B'), spaceAfter=4))
styles.add(ParagraphStyle(name='Small2x', parent=styles['BodyText'], fontName='Helvetica', fontSize=7.2, leading=8.7, textColor=colors.HexColor('#41536A'), spaceAfter=2))
styles.add(ParagraphStyle(name='Tiny2x', parent=styles['BodyText'], fontName='Helvetica', fontSize=6.2, leading=7.1, textColor=colors.HexColor('#52647A')))
styles.add(ParagraphStyle(name='HeaderWhite', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=7.0, leading=8.1, textColor=WHITE, alignment=0))
styles.add(ParagraphStyle(name='Callout2', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=12.0, leading=14.5, textColor=BLUE, backColor=LIGHT, borderPadding=7, spaceAfter=6))
styles.add(ParagraphStyle(name='Caption2', parent=styles['BodyText'], fontName='Helvetica-Oblique', fontSize=6.8, leading=8.2, textColor=colors.HexColor('#5D6F84'), spaceBefore=2, spaceAfter=3))


def P(text, style='Body2x'):
    return Paragraph(text, styles[style])


def tbl(rows, widths, font=6.7, leading=7.8):
    conv=[]
    for ri,row in enumerate(rows):
        out=[]
        for x in row:
            if isinstance(x, Paragraph):
                out.append(x)
            else:
                out.append(Paragraph(str(x), styles['HeaderWhite'] if ri == 0 else styles['Tiny2x']))
        conv.append(out)
    t=Table(conv, colWidths=widths, repeatRows=1, hAlign='LEFT')
    cmds=[
        ('BACKGROUND',(0,0),(-1,0),BLUE),
        ('TEXTCOLOR',(0,0),(-1,0),WHITE),
        ('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#B8C7D8')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
    ]
    for r in range(1,len(conv)):
        if r%2==0:
            cmds.append(('BACKGROUND',(0,r),(-1,r),colors.HexColor('#F7FAFD')))
    t.setStyle(TableStyle(cmds))
    return t


def screenshot(path, max_w=270*mm, max_h=78*mm):
    p = Path(path)
    if not p.exists():
        return P(f'[Screenshot not found: {p.name}]','Small2x')
    from PIL import Image
    with Image.open(p) as im:
        w,h=im.size
    scale=min(float(max_w)/w, float(max_h)/h)
    img=RLImage(str(p), width=w*scale, height=h*scale)
    img.hAlign='CENTER'
    return img


def header_footer(canvas, doc):
    canvas.saveState(); W,H=landscape(A4)
    canvas.setFillColor(BLUE); canvas.rect(0,H-7*mm,W,7*mm,fill=1,stroke=0)
    canvas.setFont('Helvetica',6.8); canvas.setFillColor(colors.HexColor('#66798F'))
    canvas.drawString(10*mm,7*mm,'KSISU Skillathon 2026 - Evidence-First Manufacturing Pilot')
    canvas.drawRightString(W-10*mm,7*mm,f'Page {doc.page}')
    canvas.restoreState()


def load_run(run_dir: Path):
    ratio=pd.read_csv(run_dir/'ratio_intervals.csv')
    district=pd.read_csv(run_dir/'district_priority.csv')
    rank=pd.read_csv(run_dir/'rank_stability.csv')
    corrupt=pd.read_csv(run_dir/'corruption_test_summary.csv').iloc[0]
    summary=json.loads((run_dir/'run_summary.json').read_text(encoding='utf-8'))
    audit=json.loads((run_dir/'audit_log.jsonl').read_text(encoding='utf-8').strip().splitlines()[-1])
    return ratio,district,rank,corrupt,summary,audit


def make_pdf():
    proxy_dir=OUT/'proxy_baseline'
    dgt_dir=OUT/'dgt_share_run' if (OUT/'dgt_share_run'/'run_summary.json').exists() else OUT/'dgt_run'
    if not (proxy_dir/'run_summary.json').exists():
        raise FileNotFoundError('Run proxy first: python run_gap.py --out out/proxy_baseline')
    if not (dgt_dir/'run_summary.json').exists():
        raise FileNotFoundError('Run DGT evidence-upgrade: python run_gap.py --actual-supply clean/dgt_cts_2026_karnataka_supply_nco.csv --proxy-allocation-method dgt_2026_seat_share --out out/dgt_share_run')

    proxy_ratio, proxy_district, proxy_rank, proxy_corrupt, proxy_summary, proxy_audit = load_run(proxy_dir)
    dgt_ratio, dgt_district, dgt_rank, dgt_corrupt, dgt_summary, dgt_audit = load_run(dgt_dir)

    cfg=json.loads((CLEAN/'config.json').read_text(encoding='utf-8'))
    from run_gap import CONFIG as MODEL_CONFIG
    cfg={**MODEL_CONFIG, **cfg}
    if 'occupation_prior_uncertainty' not in cfg:
        cfg['occupation_prior_uncertainty']=MODEL_CONFIG['occupation_prior_uncertainty']
    mix=pd.read_csv(CLEAN/'occupation_mix_prior.csv')
    cw=pd.read_csv(CLEAN/'crosswalk.csv')
    dgt_supply=pd.read_csv(CLEAN/'dgt_cts_2026_karnataka_supply_nco.csv')
    iti=pd.read_csv(CLEAN/'district_iti_counts.csv')
    demand_stability_path = proxy_dir/'demand_allocator_rank_stability.csv'
    demand_stability = pd.read_csv(demand_stability_path) if demand_stability_path.exists() else pd.DataFrame()
    scenario_robustness_path = OUT/'scenario_robustness.csv'
    scenario_robustness = pd.read_csv(scenario_robustness_path) if scenario_robustness_path.exists() else pd.DataFrame()

    selected_groups=[str(x) for x in cfg['selected_nco_groups']]
    selected_occ=mix[mix.nco_group_2digit.astype(str).isin(selected_groups)]
    selected_occ_share=float(selected_occ.share_within_manufacturing.sum())
    selected_course_weight=float(cw.statewide_course_weight.sum())
    mapped_seats=float(dgt_supply.loc[dgt_supply.nco_group_2digit.isin(selected_groups),'seats'].sum())
    out_scope_seats=float(dgt_supply.loc[dgt_supply.nco_group_2digit.eq('OUT_OF_SCOPE'),'seats'].sum())
    unmapped_seats=float(dgt_supply.loc[dgt_supply.nco_group_2digit.eq('UNMAPPED'),'seats'].sum())
    dgt_seats=float(dgt_supply.seats.sum())
    dgt_scale=float(dgt_audit.get('actual_to_state_seat_ratio',0))
    covered_pairs=int(dgt_audit.get('actual_covered_district_group_pairs',0))
    required_pairs=int(dgt_audit.get('actual_required_district_group_pairs',0))

    path=OUT/'KSISU_Skillathon_2026_Final_10_Page.pdf'
    doc=SimpleDocTemplate(str(path),pagesize=landscape(A4),leftMargin=8*mm,rightMargin=8*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]

    # PAGE 1
    story += [Spacer(1,20*mm),P('KSISU: Evidence-First District Skill Intelligence','Title2'),
              P('A reproducible method for sparse public labour-market evidence, explicit uncertainty, and data-collection prioritisation.','Callout2'),
              P(f"<b>Manufacturing pilot</b> &nbsp;&nbsp; <b>NCO scope:</b> {', '.join(selected_groups)} &nbsp;&nbsp; <b>Reference FY:</b> {cfg['reference_fy']} &nbsp;&nbsp; <b>Monte Carlo:</b> {cfg['monte_carlo_draws']:,} shared draws"),
              Spacer(1,5*mm),
              tbl([['What this prototype demonstrates','What it deliberately does not claim'],
                   ['Real DGT 2026 provisional district x ITI x trade supply enters the evidence pipeline','A proxy ranking is a proven district skill-gap result'],
                   ['Demand and supply are kept on separate evidence ladders','Partial DGT coverage is a complete district census'],
                   ['Uncertainty, evidence gates and human review are explicit','An official Karnataka Skill Index formula'],
                   ['Outputs include value-of-information for future onboarding','A policy recommendation without full district evidence']], [112*mm,158*mm], font=7.0),
              Spacer(1,6*mm),
              P('<b>Core message:</b> the system replaces proxy supply with real public evidence wherever available, but refuses to turn incomplete evidence into a policy call.','Callout2'),PageBreak()]

    # PAGE 2
    story += [P('1. Evidence ladder and data grain','H2b'),
              tbl([['Input','Grain','Period','Role'],
                   ['LGD district register','district','2026','canonical geography / join key'],
                   ['Udyam district employment','district','2022 / Apr-2023 publication','district allocation proxy; all-sector MSME employment'],
                   ['ASI Karnataka manufacturing','state','2022-23','state manufacturing employment base'],
                   ['NCVT MIS Karnataka ITI magnitude','state','2022','state seat magnitude / conservation benchmark'],
                   ['Historical ITI counts','district weight','2022','historical allocation weights only'],
                   ['DGT CTS-2026 provisional seat matrix','district x ITI x trade','2026','real public district/trade supply evidence'],
                   ['Occupation mix','state prior','2022-23','analyst prior until PLFS occupation-by-industry microdata is loaded'],
                   ['Trade -> NCO crosswalk','trade -> NCO','versioned','human-reviewed pilot mapping']], [60*mm,37*mm,36*mm,137*mm], font=6.55),
              Spacer(1,4*mm),
              tbl([['Run','Rows','Seats','Coverage','Policy status'],
                   ['Proxy baseline','60 analytical cells','proxy-calibrated','No district actual supply','60 NEEDS DATA'],
                   ['DGT share-calibrated upgrade','60 analytical cells','45,416 published DGT seats','58 / 60 district-group pairs; 88.0% in pilot scope','60 NEEDS DATA']], [56*mm,36*mm,43*mm,81*mm,44*mm], font=6.6),
              Spacer(1,4*mm),P('All outputs carry source provenance, year, grain and evidence status. The DGT 2026 matrix is explicitly provisional in the official source and is not treated as final seat capacity.','Small2x'),PageBreak()]

    # PAGE 3
    story += [P('2. Inputs in the workbench','H2b'),
              P('The workbench makes every research input visible before any analysis is run. This is the audit surface: a judge can see the source file, grain and period instead of trusting a hidden preprocessing step.'),
              Spacer(1,2*mm), screenshot(SHOT/'page_03_inputs_and_assumptions_dgt_selected.png', max_w=282*mm, max_h=95*mm),
              P('Figure 1. Local research inputs and model controls after the DGT provisional supply source is selected.', 'Caption2'),
              tbl([['Visible control','Current value','Interpretation'],
                   ['Opening rate','5% / 8.5% / 12%','analyst range for annual openings'],
                   ['Seat fill','50% / 81.3% / 90%','training utilization prior'],
                   ['Completion','50% / 59.3% / 70%','completion prior'],
                   ['Sector entry','20% / 30% / 40%','analyst prior pending district placement data'],
                   ['MC draws / seed','5,000 / 20261016','reproducible stochastic run']], [52*mm,55*mm,173*mm], font=6.55),PageBreak()]

    # PAGE 4
    alloc_default = str(proxy_audit.get('demand_allocation_method', cfg.get('demand_allocation_method','udyam_employment')))
    alloc_note = 'employment share (default)' if alloc_default == 'udyam_employment' else alloc_default
    story += [P('3. Demand model - allocator choice is a structural sensitivity','H2b'),
              P('District manufacturing employment is allocated from the Karnataka ASI manufacturing total using an explicit Udyam-based district share. The default run uses Udyam employment share; enterprise-unit share and a 50/50 blend are also tested because demand allocation is the weakest structural input.'),
              Spacer(1,3*mm),
              tbl([['NCO group','Share of total manufacturing employment','Status'],
                   ['72','0.25','modeled'],['74','0.15','modeled'],['Outside pilot','0.60','not modeled']], [48*mm,92*mm,140*mm], font=7.0),
              Spacer(1,3*mm),
              tbl([['Demand allocator','Definition','Use'],
                   ['udyam_employment', 'Udyam employment share', 'default baseline'],
                   ['udyam_units', 'Udyam enterprise-unit share (June 2026)', 'structural sensitivity'],
                   ['blend', '50/50 average of the two normalized shares', 'structural sensitivity']], [50*mm,124*mm,106*mm], font=6.5),
              Spacer(1,3*mm),
              tbl([['Allocator stability diagnostic','Value'],
                   ['Default allocator', alloc_note],
                   ['Mean district rank range across allocators', f"{float(proxy_audit.get('demand_allocator_rank_range_mean', float('nan'))):.2f}"],
                   ['Districts top-5 across all allocators', f"{int(proxy_audit.get('demand_allocator_robust_top5_count', 0))}"],
                   ['Within-allocator lognormal sigma', '0.35 analyst assumption; no district calibration yet']], [100*mm,180*mm], font=6.6),
              Spacer(1,3*mm),
              P('<b>Demand formula:</b> D(d,o) = ASI manufacturing base × selected district allocator share × occupation share; O(d,o) = D(d,o) × opening rate. The selected NCO shares remain 0.25 + 0.15 = 0.40 and are not normalized.'),
              P('<b>Interpretation:</b> a district priority is called structurally robust only when it remains high across the employment, enterprise-unit and blended demand allocators. The 0.35 lognormal term captures uncertainty within an allocator; allocator choice itself is tested separately.'),PageBreak()]

    # PAGE 5
    story += [P('4. Real DGT 2026 district x ITI x trade supply - evidence upgrade','H2b'),
              P('The official DGT CTS-2026 provisional dynamic seat matrix is the strongest public supply input in this build. The source states that the tentative matrix was generated from approved instructor mappings as of 08.07.2026 and remained subject to change until the 20.07.2026 cut-off. The package therefore labels it provisional, not final.'),
              Spacer(1,2*mm),
              tbl([['DGT evidence item','Result','Meaning'],
                   ['Karnataka rows',f"{len(dgt_supply):,}",'real published ITI-trade rows in uploaded DGT PDF extraction'],
                   ['Distinct ITIs',f"{dgt_supply.iti_mis_code.nunique():,}",'ITI MIS codes represented'],
                   ['Published districts',f"{dgt_supply.district.nunique()}",'29 in the provisional extraction'],
                   ['Published provisional seats',f"{dgt_seats:,.0f}",'actual DGT seat-capacity rows'],
                   ['NCO 72 + 74 mapped seats',f"{mapped_seats:,.0f} ({mapped_seats/dgt_seats*100:.1f}%)",'pilot crosswalk scope'],
                   ['OUT_OF_SCOPE seats',f"{out_scope_seats:,.0f} ({out_scope_seats/dgt_seats*100:.1f}%)",'kept in total; excluded from the 72/74 pilot'],
                   ['UNMAPPED seats',f"{unmapped_seats:,.0f} ({unmapped_seats/dgt_seats*100:.1f}%)",'still requires human review; currently zero in the expanded pilot crosswalk'],
                   ['Analytical pair coverage',f"{covered_pairs} / {required_pairs}",'Kodagu is missing from the DGT provisional file; Ballari covers the merged Ballari-Vijayanagara geography'],
                   ['Policy gate','NEEDS DATA','coverage is incomplete / provisional']], [62*mm,56*mm,146*mm], font=6.25),
              Spacer(1,2*mm), screenshot(SHOT/'page_05_real_dgt_gap_tumakuru_kalaburagi_02.png', max_w=282*mm, max_h=76*mm),
              P('Figure 2. Real DGT supply loaded into the model. Tumakuru and Kalaburagi show district-level provisional evidence, but the policy gate remains closed because coverage is incomplete.', 'Caption2'),PageBreak()]

    # PAGE 6
    story += [P('5. Supply model and scale reconciliation','H2b'),
              P('Supply is kept as a flow: seats x fill rate x completion rate x sector entry x trade-to-NCO weight. The DGT matrix is not silently substituted for the NCVT state magnitude; the two sources are reported side by side so the scale difference is visible.'),
              Spacer(1,3*mm),
              tbl([['Scale check','Value','Interpretation'],
                   ['NCVT Karnataka state seats (2022)',f"{dgt_audit.get('statewide_total_iti_seats',216788):,.0f}",'statewide magnitude benchmark'],
                   ['DGT CTS-2026 provisional seats',f"{dgt_seats:,.0f}",'real published provisional district/trade rows'],
                   ['DGT / NCVT seat ratio',f"{dgt_scale:.3f} ({dgt_scale*100:.1f}%)",'WARNING: below configured 0.50 reconciliation threshold'],
                   ['DGT ITI / historical ITI coverage',f"{dgt_audit.get('dgt_matrix_iti_total',0):,.0} ITIs; mean coverage {float(dgt_audit.get('dgt_matrix_iti_coverage_mean',0))*100:.1f}%",'approximate cross-period coverage weight; not exact census coverage'],
                   ['Mapped to NCO 72/74',f"{mapped_seats:,.0f} ({mapped_seats/dgt_seats*100:.1f}%)",'within pilot scope'],
                   ['OUT_OF_SCOPE',f"{out_scope_seats:,.0f} ({out_scope_seats/dgt_seats*100:.1f}%)",'not a mapping failure; outside current pilot'],
                   ['UNMAPPED',f"{unmapped_seats:,.0f} ({unmapped_seats/dgt_seats*100:.1f}%)",'true mapping/review remainder']], [74*mm,58*mm,132*mm], font=6.8),
              Spacer(1,4*mm),
              P('<b>Why the scale warning matters:</b> 45,416 published DGT seats represent only about one-fifth of the 2022 Karnataka NCVT seat magnitude. The DGT rows are therefore used primarily as a <b>distribution signal</b> across districts and NCO groups, not as the statewide level. District DGT shares are shrunk toward the historical ITI-count proxy in proportion to approximate matrix coverage (DGT ITIs / 2022 ITIs); a district absent from the matrix therefore retains its proxy rather than receiving zero. The allocation concentration is intentionally lower for this provisional evidence mode.'),
              Spacer(1,4*mm),
              tbl([['Coverage rule','Current state'],
                   ['Required analytical district x NCO pairs','60'],
                   ['Covered by DGT provisional file','58'],
                   ['Full-evidence gate','CLOSED'],
                   ['Policy decision status','60 NEEDS DATA']], [95*mm,155*mm], font=7.0),PageBreak()]

    # PAGE 7
    story += [P('6. Relative alignment and data-collection priority','H2b'),
              P('SCI and VOI are presented as prioritisation tools. They are not validation of the district ranking because missing district/group evidence still falls back to proxy allocation. The ranking is based on the uncapped median ratio R; SCI is shown separately as a capped coverage index.'),
              Spacer(1,2*mm), screenshot(SHOT/'page_08_data_collection_priority.png', max_w=282*mm, max_h=94*mm),
              P('Figure 3. District priority view. VOI answers where better district evidence should be collected first; it is not a claim that the top-ranked district has the largest true skill shortage.', 'Caption2'),
              tbl([['Interpretation rule','Use'],['Median R','alignment signal; can be above or below 1'],['SCI','share of modeled openings covered at min(R,1)'],['VOI','interval width x annual openings'],['Data priority','VOI adjusted by evidence/confidence; onboarding queue']], [55*mm,195*mm], font=6.7),PageBreak()]

    # PAGE 8
    robust_rows=[['District','Top-5 appearances / 6','Rank min-max','Robust across all six']]
    if not scenario_robustness.empty:
        top_rows=scenario_robustness.sort_values(['top5_appearances','rank_range','district'], ascending=[False,True,True]).head(5)
        for _, r in top_rows.iterrows():
            robust_rows.append([r['district'], str(int(r['top5_appearances'])), f"{int(r['rank_min'])}-{int(r['rank_max'])}", 'YES' if bool(r['top5_all_six']) else 'No'])
    robust_summary = json.loads((OUT/'run_summary.json').read_text(encoding='utf-8')) if (OUT/'run_summary.json').exists() else {}
    robust_names = ', '.join(robust_summary.get('robust_priority', [])) or 'None'
    rank_range_gt5 = int(robust_summary.get('districts_rank_range_above_5', 0))
    story += [P('7. Sensitivity as rank stability','H2b'),
              P('Shared Monte Carlo draws are used across districts. Rank stability is a common-system uncertainty diagnostic. The stronger judge-facing test is the six-scenario robustness table, which compares proxy and DGT-share supply routes under all three demand allocators.'),
              Spacer(1,1.5*mm), screenshot(SHOT/'page_07_rank_stability_sensitivity.png', max_w=282*mm, max_h=77*mm),
              P('Figure 4. Rank stability under shared uncertainty. The same draw structure is used across districts so relative ranking is comparable.', 'Caption2'),
              Spacer(1,1.5*mm),
              tbl(robust_rows, [80*mm,65*mm,50*mm,65*mm], font=6.9),
              Spacer(1,2*mm),
              P(f'<b>Six-scenario result:</b> {robust_names} is top-five in all six scenarios; {rank_range_gt5} districts have a rank range above 5. A robust flag is therefore a stress-test result, not a declaration of a true skill shortage. The 50/50 blend is an arbitrary midpoint sensitivity case, not an empirical estimator. The 0.35 lognormal demand term is an explicit assumption with no district-level calibration yet.'),
              PageBreak()]

    # PAGE 9
    refresh_report_path=OUT/'data_quality_report.csv'
    refresh_report=pd.read_csv(refresh_report_path) if refresh_report_path.exists() else pd.DataFrame()
    refresh_review_path=OUT/'review_queue.csv'
    refresh_review=pd.read_csv(refresh_review_path) if refresh_review_path.exists() else pd.DataFrame(columns=['path','action'])
    refresh_checked=len(refresh_report)
    refresh_unchanged=int((refresh_report['hash_status']=='UNCHANGED').sum()) if 'hash_status' in refresh_report.columns else 0
    refresh_changed=int((refresh_report['hash_status']=='CHANGED').sum()) if 'hash_status' in refresh_report.columns else 0
    iti_weight_check='30 / 30 exact'
    story += [P('8. Component B - refresh automation, lineage and human review','H2b'),
              P('Component B turns scheduled refresh from a narrative claim into an executable gate. Each registered source file is hashed, its schema and row count are checked, statewide NCVT seat movement is tested against a 20% anomaly threshold, and any review item stops publication until a human approves the update.'),
              Spacer(1,2*mm),
              tbl([['Automation check','Current run','Judge meaning'],
                   ['Registered files checked',f'{refresh_checked}','source registry is machine-audited'],
                   ['Unchanged / skipped',f'{refresh_unchanged}','no unnecessary reprocessing'],
                   ['Changed files in current baseline',f'{refresh_changed}','none in the frozen snapshot'],
                   ['Statewide seat anomaly threshold','20%','a large source shift requires review'],
                   ['Empty review queue output','header preserved','machine-readable even when no rows need review'],
                   ['Legitimate source update','`python refresh_pipeline.py --make-baseline`','approved update resets the comparison baseline']], [76*mm,55*mm,129*mm], font=6.45),
              Spacer(1,3*mm),
              tbl([['Evidence claim','Verification'],
                   ['Historical ITI allocation weights','30 / 30 analytical rows match Rajya Sabha Annexure-IV page 6; printed 275 Government + 1,227 Private = 1,502 total'],
                   ['Ballari-Vijayanagara public export','2,268 observed NCO 72/74 DGT seats; ratio and rank remain visible'],
                   ['Kodagu public export','No DGT rows; explicitly `not_observed` and retains modeled historical-ITI-weight supply'],
                   ['Suppression guardrail','Institutional aggregate data only; no personal data is ingested. Threshold 5 is a safeguard for future finer-grained data']], [82*mm,178*mm], font=6.25),
              Spacer(1,3*mm), P('The same refresh layer also records SHA-256 provenance, source URL, period and grain. Human review is a required publication step, not an exception path.'),
              PageBreak()]

    # PAGE 10
    story += [P('9. Judge demo: what KSISU can see, and what it should collect next','H2b'),
              screenshot(SHOT/'page_10_judge_demo.png', max_w=282*mm, max_h=86*mm),
              P('Figure 6. Judge-demo sequence embedded in the workbench.', 'Caption2'),
              tbl([['Demo step','What to say'],
                   ['1. Proxy baseline','This is the conservative public-data baseline.'],
                   ['2. District priority','This is a data-collection queue, not a district skill-gap leaderboard.'],
                   ['3. Load DGT 2026 real supply','Real district x ITI x trade rows replace proxy supply where they exist.'],
                   ['4. Run with loaded supply','Partial coverage remains an observed floor plus uncertain remainder.'],
                   ['5. Gap results','Show P10 / median / P90 and the policy gate.'],
                   ['6. Sensitivity','Show whether priority is stable across shared draws.'],
                   ['7. Validation','Show typo recovery, review queue, dedupe and provenance.']], [70*mm,180*mm], font=6.6),
              Spacer(1,3*mm), P('<b>One-sentence story:</b> “We use real DGT district/group seat distribution to improve the allocation, keep uncertainty where coverage is incomplete, and only unlock a district policy call when the evidence gate is satisfied.”','Callout2'),
              P('<b>Current blocker:</b> the public DGT 2026 matrix is provisional, covers 58/60 analytical district-group pairs, and its 45,416 published seats are only 20.9% of the 2022 NCVT state seat magnitude. The DGT-share run changes the district allocation using coverage-weighted DGT shares (588 DGT ITIs relative to the historical 2022 denominator), while the demand allocator is stress-tested across Udyam employment, Udyam units and their blend. The model still makes no district policy claim because evidence coverage is incomplete.'),
              P('<b>Submission note:</b> SCI, VOI, confidence and evidence gates are proposed methodology for the Skillathon, not an official Karnataka formula. The DGT source is a provisional 2026 dynamic seat matrix, not a final frozen capacity table.','Small2x')]

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return path

if __name__=='__main__':
    print(make_pdf())
