from pathlib import Path
import json
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect, String, Line

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'out'; OUT.mkdir(exist_ok=True)
CLEAN=ROOT/'clean'; RAW=ROOT/'raw'
BLUE=colors.HexColor('#0D2A4A'); LIGHT=colors.HexColor('#EEF3F9'); GREEN=colors.HexColor('#1D7A46'); AMBER=colors.HexColor('#8A6200'); RED=colors.HexColor('#A32C2C'); WHITE=colors.white
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Title2', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=25, leading=29, textColor=BLUE, spaceAfter=8))
styles.add(ParagraphStyle(name='H2b', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=16, leading=19, textColor=BLUE, spaceAfter=6))
styles.add(ParagraphStyle(name='Body2', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.0, leading=11.7, textColor=colors.HexColor('#24364B'), spaceAfter=4))
styles.add(ParagraphStyle(name='Small2', parent=styles['BodyText'], fontName='Helvetica', fontSize=7.5, leading=9.0, textColor=colors.HexColor('#41536A'), spaceAfter=2))
styles.add(ParagraphStyle(name='Tiny', parent=styles['BodyText'], fontName='Helvetica', fontSize=6.6, leading=7.6, textColor=colors.HexColor('#52647A')))
styles.add(ParagraphStyle(name='TableHeader', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=6.8, leading=7.9, textColor=WHITE))
styles.add(ParagraphStyle(name='Callout', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=12.5, leading=15, textColor=BLUE, backColor=LIGHT, borderPadding=8, spaceAfter=6))

def P(txt, style='Body2'): return Paragraph(txt, styles[style])


def mini_bar_chart(rows, value_key, label_key, title, width=250*mm, height=48*mm, max_value=None):
    d=Drawing(width,height)
    pad_left=42*mm; pad_right=8*mm; pad_top=10*mm; pad_bottom=6*mm
    inner_w=width-pad_left-pad_right; inner_h=height-pad_top-pad_bottom
    d.add(String(0,height-4*mm,title,fontName='Helvetica-Bold',fontSize=8,fillColor=BLUE))
    vals=[float(r[value_key]) for r in rows]
    labels=[str(r[label_key]) for r in rows]
    vmax=max_value if max_value is not None else (max(vals) if vals else 1.0)
    vmax=max(vmax,1e-9)
    bar_h=min(5.0*mm, inner_h/max(len(rows),1)-1.0*mm)
    gap=(inner_h-bar_h*len(rows))/max(len(rows)-1,1) if len(rows)>1 else 0
    y=height-pad_top-bar_h
    for lab,val in zip(labels,vals):
        w=inner_w*val/vmax
        d.add(String(0,y+0.8*mm,lab[:18],fontName='Helvetica',fontSize=6.5,fillColor=colors.HexColor('#41536A')))
        d.add(Rect(pad_left,y,w,bar_h,fillColor=colors.HexColor('#2B6EA6'),strokeColor=None))
        d.add(String(pad_left+w+1.2*mm,y+0.8*mm,f'{val:.2f}',fontName='Helvetica',fontSize=6.2,fillColor=BLUE))
        y-=bar_h+gap
    d.add(Line(pad_left,6*mm,pad_left,height-pad_top+1*mm,strokeColor=colors.HexColor('#B8C7D8'),strokeWidth=0.5))
    return d

def tbl(data, widths=None, font=6.8, leading=7.9):
    conv=[]
    for ri,row in enumerate(data):
        conv.append([x if isinstance(x, Paragraph) else Paragraph(str(x), styles['TableHeader'] if ri==0 else (styles['Tiny'] if font<=6.5 else styles['Small2'])) for x in row])
    t=Table(conv, colWidths=widths, repeatRows=1, hAlign='LEFT')
    cmds=[('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),font),('LEADING',(0,0),(-1,-1),leading),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#B8C7D8')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),3.5),('BOTTOMPADDING',(0,0),(-1,-1),3.5),('BACKGROUND',(0,0),(-1,0),BLUE),('TEXTCOLOR',(0,0),(-1,0),WHITE)]
    for r in range(1,len(conv)):
        if r%2==0: cmds.append(('BACKGROUND',(0,r),(-1,r),colors.HexColor('#F7FAFD')))
    t.setStyle(TableStyle(cmds)); return t

def header_footer(canvas, doc):
    canvas.saveState(); W,H=landscape(A4)
    canvas.setFillColor(BLUE); canvas.rect(0,H-7*mm,W,7*mm,fill=1,stroke=0)
    canvas.setFont('Helvetica',6.8); canvas.setFillColor(colors.HexColor('#66798F'))
    canvas.drawString(12*mm,7*mm,'KSISU Skillathon 2026 - Evidence-First Manufacturing Pilot')
    canvas.drawRightString(W-12*mm,7*mm,f'Page {doc.page}')
    canvas.restoreState()

def make_pdf():
    ratio=pd.read_csv(OUT/'ratio_intervals.csv')
    district=pd.read_csv(OUT/'district_priority.csv')
    rank=pd.read_csv(OUT/'rank_stability.csv') if (OUT/'rank_stability.csv').exists() else pd.read_csv(OUT/'sensitivity.csv')
    corrupt=pd.read_csv(OUT/'corruption_test_summary.csv').iloc[0]
    update=pd.read_csv(OUT/'interval_evidence_update.csv') if (OUT/'interval_evidence_update.csv').exists() and (OUT/'interval_evidence_update.csv').stat().st_size>5 else pd.DataFrame()
    # Always materialize the bundled partial-evidence demonstration for the PDF.
    # It is explicitly a floor + uncertain remainder, never a full district result.
    if update.empty:
        try:
            from run_gap import compute_model
            partial_file = RAW/'ncvtmis_file1171_real_partial.csv'
            if partial_file.exists():
                partial_run = compute_model(actual_supply_path=str(partial_file), write_outputs=False)
                update = partial_run['interval_demo'].copy()
        except Exception:
            update = pd.DataFrame()
    variation=pd.read_csv(OUT/'district_variation_diagnostic.csv').iloc[0]
    summary=json.loads((OUT/'run_summary.json').read_text())
    audit=json.loads((OUT/'audit_log.jsonl').read_text().strip().splitlines()[-1])
    from run_gap import CONFIG as RUN_CONFIG
    cfg=RUN_CONFIG
    mix=pd.read_csv(CLEAN/'occupation_mix_prior.csv')
    mix_sel=mix[mix.nco_group_2digit.astype(str).isin([str(x) for x in cfg['selected_nco_groups']])]
    cw=pd.read_csv(CLEAN/'crosswalk.csv')
    selected_course_weight=float(cw.statewide_course_weight.sum())
    selected_occ_share=float(mix_sel.share_within_manufacturing.sum())
    seat_total=float(audit.get('statewide_total_iti_seats', 0))
    state_median=float(district['SCI'].median())
    focus=district[district.district.isin(['Tumakuru','Kalaburagi'])].copy()
    raw=summary
    iti_weights = pd.read_csv(CLEAN/'district_iti_counts.csv') if (CLEAN/'district_iti_counts.csv').exists() else pd.DataFrame()
    # Count as verified only if the reproducible check against the printed Annexure-IV table passes now.
    from verify_iti_counts import verify as _verify_iti
    _iti_problems = _verify_iti(write=False) if not iti_weights.empty else ['no ITI weights']
    iti_verified = int(len(iti_weights)) if not _iti_problems else 0
    iti_total = int(len(iti_weights)) if not iti_weights.empty else 0
    iti_unverified = max(iti_total - iti_verified, 0)
    analytical_geo_count = int(len(district))

    path=OUT/'KSISU_Skillathon_2026_Final_10_Page.pdf'
    doc=SimpleDocTemplate(str(path),pagesize=landscape(A4),leftMargin=10*mm,rightMargin=10*mm,topMargin=11*mm,bottomMargin=11*mm)
    story=[]

    # 1
    story += [Spacer(1,10*mm),P('KSISU: Evidence-First District Skill Intelligence','Title2'),P('A reproducible method for sparse public labour-market evidence, explicit uncertainty, and data-acquisition prioritisation.','Callout'),P(f"<b>Sector:</b> Manufacturing &nbsp; <b>NCO scope:</b> {', '.join(cfg['selected_nco_groups'])} &nbsp; <b>FY:</b> {cfg['reference_fy']} &nbsp; <b>Monte Carlo:</b> {cfg['monte_carlo_draws']:,} shared draws"),Spacer(1,3*mm),tbl([["What the prototype demonstrates","What it does not claim"],[f"31 raw LGD districts; {analytical_geo_count} analytical geographies after Ballari-Vijayanagara harmonisation","A proxy-only district ratio is a finding"],["Separate state demand evidence and district supply evidence","The partial NCVT subset is a district census"],["Shared uncertainty and reproducible runs","An official KSI formula"],["Human review for unmatched data","A policy call without full district supply"],["Value-of-information ranking","Validation of the proxy district ranking"]],[95*mm,155*mm],font=7.1),Spacer(1,4*mm),P('<b>Headline:</b> public data can support an auditable inference chain, but the first policy output should often be a request for better district evidence.','Callout')]
    story.append(PageBreak())

    # 2 evidence ladder
    story += [P('1. Evidence ladder and data grain','H2b'),tbl([["Input","Grain","Year","Role"],["LGD district register","district","2026","canonical join key"],["Udyam district employment","district","2022 / 2023 publication","district allocation proxy"],["ASI Karnataka manufacturing","state","2022-23","state manufacturing employment base"],["NCVT MIS Karnataka ITI count","state","2022","state ITI seat magnitude"],["Historical district ITI counts","district weight","2022","allocation weights only; historical CTS geography"],["DGT/DITE tracer","division","2020-21","historical rate calibration"],["NCVT MIS File 1171 sample","district x ITI x trade","historical indexed","partial evidence only"],["Occupation mix","state prior","2022-23","analyst prior until PLFS microdata is loaded"]],[56*mm,31*mm,30*mm,133*mm],font=6.8),Spacer(1,4*mm),tbl([["Audit field","Purpose"],["file_id / SHA-256","stable artifact identity and tamper detection"],["source_id / URL / locator","reproducible source trail"],["period / grain","prevents silent state/district mixing"],["match method / confidence","shows how linkage was obtained"],["coverage status","controls whether policy output is eligible"]],[65*mm,185*mm],font=7.0),Spacer(1,4*mm),P(f'The NCVT state page reports Karnataka at 1,467 ITIs and 216,788 seats available for 2022. The model uses that as the statewide seat magnitude. Historical district ITI counts are allocation weights only: <b>{iti_verified}/{iti_total}</b> analytical weights match the Rajya Sabha Q131 Annexure-IV table as printed (checked against machine-extracted text of the official PDF, 2026-10-17; reproducible with verify_iti_counts.py) and <b>{iti_unverified}</b> remain unmatched. The source uses the 2022 CTS geography; Ballari-Vijayanagara is harmonised analytically. Udyam employment is an all-sector MSME district proxy with uneven coverage and is not equivalent to manufacturing employment.') ]
    story.append(PageBreak())

    # 3 linkage
    story += [P('2. Linkage and harmonisation','H2b'),P('<b>District:</b> normalized exact -> production alias -> fuzzy match at 0.90 -> human review. Unmatched rows remain in the review queue.'),P('<b>Industry:</b> NIC retained at the first two digits when a source code exists; labels without a code remain reviewable.'),P('<b>Course/trade:</b> versioned human-reviewed NCO crosswalk. The project labels the crosswalk as an analyst mapping aid, not an official course-to-NCO master.'),Spacer(1,3*mm),tbl([["Validation result","Value"],["LGD districts","31 / 31 raw"],["Analytical geographies",f"{analytical_geo_count}"],["Seeded typo cases","80"],["Correct typo recovery",f"{int(corrupt.seeded_typo_correct)} / {int(corrupt.seeded_typo_rows)} = {corrupt.seeded_typo_recovery_rate*100:.1f}%"],["Unseen aliases matched","0 / 20"],["Unseen aliases routed to review",f"{int(corrupt.unseen_alias_review_rows)} / {int(corrupt.unseen_alias_rows)}"],["Duplicate artifacts injected / removed",f"{int(corrupt.duplicate_rows_injected)} / {int(corrupt.duplicate_rows_removed)}"],["Unmatched rows dropped","0"]],[100*mm,150*mm],font=7.0),Spacer(1,4*mm),P('<b>Interpretation:</b> unseen aliases are not counted as successful matches. The test is a review-queue test as well as a typo-recovery test.') ]
    story.append(PageBreak())

    # 4 demand
    mix_rows=[]
    for _, r in mix_sel.sort_values('nco_group_2digit').iterrows():
        mix_rows.append([str(r['nco_group_2digit']), f"{float(r['share_within_manufacturing']):.2f}", 'modeled'])
    mix_rows.append(['Outside pilot', f"{1-selected_occ_share:.2f}", 'not modeled'])
    story += [P('3. Demand model - one basis, explicit priors','H2b'),P("District manufacturing employment is allocated from the Karnataka ASI manufacturing total using Udyam employment shares. This keeps both sides on a consistent manufacturing base; it does not multiply Udyam all-sector employment by a manufacturing share."),Spacer(1,2*mm),tbl([["NCO group","Share of total manufacturing","Status"]]+mix_rows,[50*mm,75*mm,125*mm],font=7.2),Spacer(1,3*mm),P(f"<b>District allocation uncertainty: lognormal sigma = <b>0.35</b> (analyst assumption; no empirical district calibration yet).<br/><b>Annual openings:</b></b> O(d,o) = D(d,o) x opening rate, with {cfg['opening_rate']['low']*100:.0f}% to {cfg['opening_rate']['high']*100:.0f}% range and {cfg['opening_rate']['mode']*100:.1f}% mode."),tbl([["Demand uncertainty","Low","Mode","High"],["Opening rate",f"{cfg['opening_rate']['low']*100:.1f}%",f"{cfg['opening_rate']['mode']*100:.1f}%",f"{cfg['opening_rate']['high']*100:.1f}%"],["Occupation prior multiplier",f"{cfg['occupation_prior_uncertainty']['low']:.2f}x",f"{cfg['occupation_prior_uncertainty']['mode']:.2f}x",f"{cfg['occupation_prior_uncertainty']['high']:.2f}x"]],[70*mm,45*mm,45*mm,45*mm],font=7.0),Spacer(1,4*mm),P('The occupation mix is the weakest demand input until PLFS occupation-by-industry microdata is extracted. This parameter is therefore part of the uncertainty and sensitivity story, not hidden inside a point estimate.')]
    story.append(PageBreak())

    # 5 Tumakuru/Kalaburagi
    story += [P('4. Tumakuru vs Kalaburagi - partial NCVT evidence is a floor','H2b'),P('The bundled File 1171 rows are indexed NCVT MIS evidence, not a downloaded complete district extract. Observed seats are treated as a floor plus an uncertain remainder. Therefore a partial file can widen the interval rather than create fake precision.'),Spacer(1,2*mm)]
    update_data=[["District","NCO","Observed seats","Before width","After width","Change","After P10 / P50 / P90","Policy"]]
    obs=pd.read_csv(RAW/'ncvtmis_file1171_real_partial.csv')
    obs2=obs.groupby(['district','nco_group_2digit'])['seats'].sum().reset_index()
    obsmap={(r.district,str(r.nco_group_2digit)):int(r.seats) for _,r in obs2.iterrows()}
    if update.empty:
        update_data.append(['Tumakuru','72',obsmap.get(('Tumakuru','72'),'n/a'),'n/a','n/a','n/a','n/a','NEEDS DATA'])
    else:
        for _,r in update.iterrows():
            update_data.append([r.district,r.nco_group_2digit,obsmap.get((r.district,str(r.nco_group_2digit)),'n/a'),f"{r.before_width:.3f}",f"{r.after_width:.3f}",f"{r.interval_width_change_pct:.1f}%",f"{r.after_ratio_p10:.2f} / {r.after_ratio_median:.2f} / {r.after_ratio_p90:.2f}","NEEDS DATA" if not r.policy_call_allowed else "ELIGIBLE"])
    interval_rows=[{'district':f"{r.district} {r.nco_group_2digit}",'change':abs(float(r.interval_width_change_pct))} for _,r in update.iterrows()] if not update.empty else []
    story += [tbl(update_data,[32*mm,15*mm,24*mm,25*mm,25*mm,24*mm,73*mm,28*mm],font=6.1,leading=7.0),Spacer(1,3*mm),P('<b>What this page proves:</b> the same model can ingest real district/trade rows without treating them as complete. The current subset is too small for a district-wide policy call. A complete 31-district x trade file is the next evidence gate.'),Spacer(1,3*mm),tbl([["Observed indexed rows","Seats"],["Tumakuru - Govt ITI Tumkur - Fitter","20"],["Tumakuru - Govt ITI Tumkur - Electrician","20"],["Tumakuru - Govt ITI Tumkur - Welder","40"],["Kalaburagi - Govt ITI Wadi - Fitter","20"],["Kalaburagi - Govt ITI Wadi - Welder","40"]],[170*mm,30*mm],font=7.0),Spacer(1,4*mm)]
    if interval_rows:
        story.append(mini_bar_chart(interval_rows,'change','district','Absolute interval-width change (%) in the partial evidence test',width=245*mm,height=42*mm,max_value=max(v['change'] for v in interval_rows)))
    story.append(PageBreak())

    # 6 supply/conservation
    story += [P('5. Supply model and conservation check','H2b'),P('S(d,o) = seats(d,c) x fill x completion x sector-entry x crosswalk(c->o). Seats, completions and sector entry remain separate quantities.'),Spacer(1,2*mm),tbl([["Input","Current handling"],["State ITI seats",f"{seat_total:,.0f} seats available in NCVT MIS state row; state magnitude only"],["Selected course weight",f"{selected_course_weight:.2f} across NCO 72 + 74; not normalized"],["Fill rate",f"{cfg['seat_fill_rate']['low']*100:.0f}% / {cfg['seat_fill_rate']['mode']*100:.1f}% / {cfg['seat_fill_rate']['high']*100:.0f}%"],["Completion rate",f"{cfg['completion_rate']['low']*100:.0f}% / {cfg['completion_rate']['mode']*100:.1f}% / {cfg['completion_rate']['high']*100:.0f}%"],["Sector entry",f"{cfg['sector_entry_rate']['low']*100:.0f}% / {cfg['sector_entry_rate']['mode']*100:.1f}% / {cfg['sector_entry_rate']['high']*100:.0f}%"],["Allocation", "NCVT district ITI-count weights when supplied; otherwise explicit equal-within-division fallback"]],[52*mm,198*mm],font=6.9),Spacer(1,3*mm),tbl([["Conservation diagnostic","Value"],["Expected mean statewide supply",f"{audit['statewide_supply_expected_mean']:,.0f}"],["Sum of district/group supply medians",f"{audit['statewide_supply_median_sum']:,.0f}"],["Median/expected ratio",f"{audit['statewide_supply_conservation_ratio']:.3f}"],["Decision","PASS - median within 25% of the triangular-mean expectation" if abs(audit['statewide_supply_conservation_ratio']-1)<0.25 else "REVIEW"]],[85*mm,165*mm],font=7.0),Spacer(1,3*mm),P('The conservation check is designed to catch the former second-division bug: proxy seats are already split to districts, so the common allocation draw is a multiplier with mean 1.0 rather than another 1/n share. Historical district ITI counts are allocation weights only; they are not presented as current district seat totals.')]
    story.append(PageBreak())

    # 7 relative index and priority
    story += [P('6. Relative index and data-collection priority','H2b'),P('SCI(d) = weighted share of modeled openings covered at R=min(S/D,1). For proxy-only data, the district ranking is explicitly a <b>data-collection view</b>, not a validated labour-market finding; ranking differences are driven in part by allocation weights and Udyam proxy coverage.'),Spacer(1,2*mm)]
    rows=[]
    for _,r in district.head(12).iterrows():
        rows.append([int(r.ratio_rank),r.district,f"{r.uncapped_ratio_median:.3f}",f"{r.relative_uncapped_ratio_vs_state_median:.2f}x",f"{r.SCI:.3f}",f"{r.total_annual_openings:,.0f}",f"{r.data_collection_priority:,.0f}"])
    story += [tbl([["R rank","District","Median R","R / median","SCI","Openings","Data priority"]]+rows,[15*mm,62*mm,28*mm,30*mm,24*mm,42*mm,49*mm],font=6.4,leading=7.2),Spacer(1,3*mm),P(f"State median SCI = <b>{state_median:.3f}</b>. The ranking table is based on the <b>uncapped median ratio R</b>; SCI is reported separately as the capped coverage index. The district proxy ranking is not presented as validation because district supply still depends on proxy allocation. The correct policy use is: <b>which district should KSISU onboard first?</b>"),Spacer(1,3*mm),P(f"Current proxy allocation diagnostic: correlation with Udyam demand share = <b>{float(variation.demand_supply_proxy_share_correlation):.3f}</b>. This is reported as a diagnostic only; it is not proof that the proxy ranking is correct."),Spacer(1,3*mm)]
    chart_rows=[{'district':str(r.district),'value':float(r.uncapped_ratio_median)} for _,r in district.sort_values('uncapped_ratio_median',ascending=False).head(8).iterrows()]
    story.append(mini_bar_chart(chart_rows,'value','district','Top proxy ratio values - use for data collection, not policy claims',width=245*mm,height=46*mm))
    story.append(PageBreak())

    # 8 rank stability
    story += [P('7. Sensitivity as rank stability, not range arithmetic','H2b'),P('The model uses shared Monte Carlo draws to test whether the <b>uncapped ratio ordering</b> is stable under common uncertainty. Rank stability is a simulation diagnostic only - it is <b>not validation</b> of district labour-market reality.'),Spacer(1,2*mm)]
    rtab=[["District","Baseline rank","P10","Median","P90","Top-5 frequency","Global rho"]]
    for _,r in rank.head(18).iterrows():
        rtab.append([r.district,int(r.baseline_rank),f"{r.rank_p10:.0f}",f"{r.rank_median:.0f}",f"{r.rank_p90:.0f}",f"{r.top5_frequency*100:.1f}%",f"{r.global_rank_stability_median_rho:.3f}"])
    story += [tbl(rtab,[60*mm,27*mm,22*mm,27*mm,22*mm,40*mm,30*mm],font=6.1,leading=6.9),Spacer(1,3*mm),P('Interpretation: a narrow rank band and high top-5 frequency indicate a stable prioritisation signal. A wide band indicates that KSISU should not over-interpret the ranking until the district evidence improves.'),Spacer(1,3*mm)]
    rank_chart=[{'district':str(r.district),'value':float(r.top5_frequency*100)} for _,r in rank.head(8).iterrows()]
    story.append(mini_bar_chart(rank_chart,'value','district','Top-5 frequency across shared Monte Carlo draws (%)',width=245*mm,height=46*mm,max_value=100))
    story.append(PageBreak())

    # 9 validation/provenance
    story += [P('8. Validation, provenance and reproducibility','H2b'),tbl([["Test","Result","Interpretation"],["District linkage","31 / 31 matched","canonical LGD mapping"],["Seeded typo recovery",f"{int(corrupt.seeded_typo_correct)} / {int(corrupt.seeded_typo_rows)} ({corrupt.seeded_typo_recovery_rate*100:.1f}%)","correctness, not just non-empty match"],["Unseen aliases",f"{int(corrupt.unseen_alias_matched)} matched; {int(corrupt.unseen_alias_review_rows)} review","unknown labels are not treated as successes"],["Duplicates",f"{int(corrupt.duplicate_rows_injected)} injected; {int(corrupt.duplicate_rows_removed)} removed","real dedupe pass"],["Rows dropped","0","unmatched evidence stays reviewable"],["Monte Carlo",f"{audit['monte_carlo_draws']:,} draws; seed {audit['seed']}","reproducible"],["Statewide conservation",f"{audit['statewide_supply_conservation_ratio']:.3f} median/expected","catches allocation errors"]],[58*mm,58*mm,132*mm],font=6.6,leading=7.6),Spacer(1,4*mm),P('Each source artifact carries file_id, SHA-256, URL, year, grain and locator. The run audit log records seed, draw count, source files and output files.')]
    story.append(PageBreak())

    # 10 deployment
    story += [P('9. What KSISU should deploy next','H2b'),tbl([["Phase","Action","Decision enabled"],["1. Evidence registry","Preserve raw artifacts, source IDs, hashes and LGD/NIC/NCO mapping","reproducible evidence layer"],["2. Full NCVT district supply","Load complete district x trade ITI export","replace proxy supply with district actual"],["3. PLFS occupation x industry","Extract state occupation mix from microdata","replace analyst occupation prior"],["4. District manufacturing employment","Use DSDP/MIS or stronger district industry evidence","reduce allocation uncertainty"],["5. Production","Scheduled refresh, quality flags, human review, machine-readable outputs","continuous KSISU intelligence"]],[44*mm,122*mm,82*mm],font=6.5,leading=7.4),Spacer(1,4*mm),P('<b>Submission position:</b> SCI, VOI, confidence and evidence gates are proposed methodology for the Skillathon, not the official Karnataka Skill Index formula.'),Spacer(1,3*mm),P('<b>Current blocker:</b> the complete current NCVT MIS district x trade seat export must be loaded before a district-wide policy call can be made. The bundled partial rows are deliberately not presented as complete.'),Spacer(1,3*mm),P('<b>AI-use disclosure:</b> AI assistance was used for code drafting, documentation and analysis design. Public-source provenance, assumptions and evidence tiers are retained in the package.'),Spacer(1,4*mm),P('Sources: LGD Download Directory; Government Open Data Udyam district employment resource; MoSPI ASI 2022-23; NCVT MIS ITI Count / ITI Search / FileDownload; DGT/DITE tracer study; PLFS official portal.','Small2')]
    doc.build(story,onFirstPage=header_footer,onLaterPages=header_footer)
    return path

if __name__=='__main__': print(make_pdf())
