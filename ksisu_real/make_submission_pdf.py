from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib.units import mm

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'out'
FIG=OUT/'figures'
FIG.mkdir(exist_ok=True)

# data
ratio=pd.read_csv(OUT/'ratio_intervals.csv')
district=pd.read_csv(OUT/'district_priority.csv')
sens=pd.read_csv(OUT/'sensitivity.csv')
corr=pd.read_csv(OUT/'corruption_test_summary.csv')
san=pd.read_csv(OUT/'sanity_summary.csv')

# charts
plt.figure(figsize=(8.2,3.2))
top=district.head(10).sort_values('VOI')
plt.barh(top['district'], top['VOI'])
plt.xlabel('VOI = interval width × annual openings')
plt.title('Top districts for data onboarding')
plt.tight_layout(); plt.savefig(FIG/'voi.png', dpi=180); plt.close()

plt.figure(figsize=(8.2,3.2))
ss=sens.groupby('parameter')['absolute_effect'].mean().sort_values()
plt.barh(ss.index, ss.values)
plt.xlabel('Mean absolute effect on alignment ratio')
plt.title('Sensitivity: which assumption moves the ratio most?')
plt.tight_layout(); plt.savefig(FIG/'sensitivity.png', dpi=180); plt.close()

focus=ratio[ratio['district'].isin(['Tumakuru','Kalaburagi'])]
plt.figure(figsize=(8.2,3.2))
for g,grp in focus.groupby('district'):
    plt.errorbar(grp['nco_group_2digit'], grp['ratio_median'], yerr=[grp['ratio_median']-grp['ratio_p10'], grp['ratio_p90']-grp['ratio_median']], fmt='o', label=g)
plt.axhline(1, linestyle='--')
plt.ylabel('Supply / annual openings')
plt.xlabel('NCO group')
plt.title('Worked illustration: proxy-mode intervals')
plt.legend()
plt.tight_layout(); plt.savefig(FIG/'focus.png', dpi=180); plt.close()

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Title2', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=24, leading=28, textColor=colors.HexColor('#0f2747'), alignment=TA_CENTER, spaceAfter=12))
styles.add(ParagraphStyle(name='H1x', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=17, leading=20, textColor=colors.HexColor('#0f2747'), spaceAfter=9))
styles.add(ParagraphStyle(name='H2x', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor('#234f7d'), spaceAfter=6))
styles.add(ParagraphStyle(name='Bodyx', parent=styles['BodyText'], fontSize=9.5, leading=13, spaceAfter=6))
styles.add(ParagraphStyle(name='Smallx', parent=styles['BodyText'], fontSize=7.5, leading=10, textColor=colors.HexColor('#4c5b6a')))
styles.add(ParagraphStyle(name='Callout', parent=styles['BodyText'], fontSize=11, leading=15, backColor=colors.HexColor('#eef5ff'), borderColor=colors.HexColor('#9ab9dd'), borderWidth=0.7, borderPadding=8, spaceBefore=7, spaceAfter=10))

pdf=OUT/'KSISU_Skillathon_2026_Research_Draft.pdf'
doc=SimpleDocTemplate(str(pdf), pagesize=A4, rightMargin=15*mm,leftMargin=15*mm,topMargin=14*mm,bottomMargin=14*mm)
story=[]

# 1
story += [Spacer(1,18*mm), Paragraph('KSISU Skillathon 2026', styles['Title2']), Paragraph('A Reproducible Method for Identifying Where District Data Is Missing - and Which District to Onboard First', ParagraphStyle('sub', parent=styles['Bodyx'], fontSize=13, alignment=TA_CENTER, leading=18, textColor=colors.HexColor('#334e68'))), Spacer(1,10*mm)]
story.append(Paragraph('Manufacturing pilot • NCO 72 / 74 / 81 • 2022-23 reference year', styles['Callout']))
story.append(Paragraph('The proposal does not claim an official Karnataka Skill Index formula. It demonstrates a transparent public-data method that separates observed inputs from proxies, propagates uncertainty, and turns uncertainty itself into an onboarding decision.', styles['Bodyx']))
story.append(Spacer(1,8*mm))
story.append(Paragraph('Core output: a district priority list for where KSISU should acquire better district trade-demand and ITI-supply data first.', styles['H1x']))
story.append(PageBreak())

# 2
story += [Paragraph('1. The problem is not the dashboard', styles['H1x']),
          Paragraph('Karnataka has multiple labour-market data streams, but they do not share the same grain, identifiers, time basis, or completeness. The challenge therefore is not to merge two clean tables; it is to build a defensible evidence chain from heterogeneous public sources to a policy action.', styles['Bodyx']),
          Paragraph('This pilot narrows the analytical question to a tractable use case: compare ITI trade supply with manufacturing occupation openings for NCO groups 72, 74 and 81. When district-actual supply is missing, the system does not invent it; it estimates a proxy, exposes the uncertainty, and asks where better data would have the largest decision value.', styles['Callout'])]
flow=[['Layer','What is observed / estimated'],['Source registry','file_id, SHA-256, source, period, grain, version'],['District key','LGD code + alias + fuzzy match + human review'],['Demand','State manufacturing base + district proxy allocation + NCO mix'],['Supply','District trade seats if available; otherwise transparent proxy'],['Inference','5,000 shared-draw Monte Carlo alignment ratio'],['Decision','Proxy-only -> NEEDS DATA; actual supply -> provisional gap/surplus/data-needed'],['Onboarding','VOI = interval width × annual openings']]
t=Table(flow, colWidths=[42*mm,138*mm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0f2747')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#c8d2df')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fc')])]))
story += [t, PageBreak()]

# 3
story += [Paragraph('2. Harmonisation is a scored method, not a string replace', styles['H1x']),
          Paragraph('District matching is a cascade: exact normalised name → known alias → fuzzy match at 0.90 → human review. Every match records the method and confidence. Unmatched rows are never dropped.', styles['Bodyx'])]
match=[['Step','Example','Output'],['Exact','Bengaluru Urban','LGD code + method=exact'],['Alias','Gulbarga → Kalaburagi','LGD code + method=alias'],['Fuzzy','Chikkaballpura → Chikkaballapur','LGD code + method=fuzzy'],['Review','Unknown district label','unmatched.csv + human review queue']]
t=Table(match, colWidths=[28*mm,70*mm,82*mm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#234f7d')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#c8d2df')),('VALIGN',(0,0),(-1,-1),'TOP')]))
story += [t, Spacer(1,5*mm), Paragraph('For occupations, the pilot restricts the analysis to NCO groups 72, 74 and 81. A versioned course/trade → NCO crosswalk is used for ITI supply. When PLFS unit-level occupation-by-industry data is available, the analyst prior can be replaced without changing the downstream model.', styles['Bodyx']), PageBreak()]

# 4 Demand
story += [Paragraph('3. Demand model: one base, one allocation rule', styles['H1x']),
          Paragraph('<b>State manufacturing base:</b> Karnataka selected-manufacturing persons engaged in ASI 2022-23 = 1,166,555.', styles['Bodyx']),
          Paragraph('<b>District proxy:</b> allocate that state manufacturing base using the district share of Udyam registered-employment. This is explicitly a proxy because Udyam employment is not a manufacturing-only labour census.', styles['Bodyx']),
          Paragraph('<b>Occupation mix:</b> restrict to NCO 72/74/81 and normalise the versioned prior. Replace with observed PLFS unit-level occupation-by-industry shares when available.', styles['Bodyx']),
          Paragraph('<b>Annual openings:</b> opening rate is triangular 5%-8.5%-12%.', styles['Bodyx'])]
formula=Table([['Quantity','Formula'],['District manufacturing employment proxy','M_d = M_state × UdyamShare_d'],['Occupation stock','E_d,o = M_d × m_o'],['Annual openings','O_d,o = E_d,o × r_open'],['Alignment ratio','R_d,o = S_d,o / O_d,o']], colWidths=[60*mm,120*mm])
formula.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0f2747')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#c8d2df')),('VALIGN',(0,0),(-1,-1),'TOP')]))
story += [Spacer(1,4*mm), formula, Image(str(FIG/'focus.png'), width=170*mm, height=66*mm), PageBreak()]

# 5 supply
story += [Paragraph('4. Supply model: seats are not graduates', styles['H1x']),
          Paragraph('The supply equation keeps flows separate: <b>Seats × Fill × Completion × Sector entry</b>. A seat is never counted as a graduate, and completions are never added to seats.', styles['Bodyx'])]
sv=[['Mode','Seat source','Evidence'],['Proxy mode','NCVT MIS Karnataka state seats + DGT division structure + district Udyam allocation','transparent but not district-actual'],['District-actual mode','NCVT MIS / DGT / Karnataka district-trade extract loaded by user','replaces proxy seats for those districts']]
t=Table(sv,colWidths=[32*mm,88*mm,60*mm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#234f7d')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#c8d2df')),('VALIGN',(0,0),(-1,-1),'TOP')]))
story += [t, Spacer(1,4*mm), Paragraph('The public NCVT MIS ITI Count page reports Karnataka with 1,467 ITIs and 216,772 seats available in 2022. NCVT MIS also exposes district/trade/seat fields in downloadable ITI extracts, which is the preferred input for the live demonstration.', styles['Bodyx']), Paragraph('Proxy-only results are not treated as empirical district gaps. They are used to rank the next data collection action.', styles['Callout']), PageBreak()]

# 6 decision
counts=ratio['decision_status'].value_counts()
story += [Paragraph('5. Policy rule: do not overclaim the proxy run', styles['H1x']),
          Paragraph(f"The current bundled run contains {len(ratio)} district×occupation rows. The mathematical interval identifies {int((ratio.signal=='GAP').sum())} cells with p90<1, but because district supply is still proxy-based, the policy-facing status remains NEEDS DATA. This is intentional.", styles['Callout']),
          Paragraph('Once a district-actual ITI trade file is loaded, the same model can produce PROVISIONAL GAP / PROVISIONAL SURPLUS / NEEDS DATA for those districts. That creates a visible bridge from public-data inference to real KSISU onboarding.', styles['Bodyx'])]
priority=district.head(10)[['priority_rank','district','SCI','VOI','mean_confidence']].copy()
priority.columns=['Rank','District','SCI','VOI','Confidence']
priority['SCI']=priority['SCI'].map(lambda x:f'{x:.3f}')
priority['VOI']=priority['VOI'].map(lambda x:f'{x:,.0f}')
priority['Confidence']=priority['Confidence'].map(lambda x:f'{100*x:.0f}%')
t=Table([priority.columns.tolist()]+priority.values.tolist(), colWidths=[18*mm,55*mm,25*mm,35*mm,35*mm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0f2747')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#c8d2df')),('ALIGN',(2,1),(-1,-1),'RIGHT'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fc')])]))
story += [t, Image(str(FIG/'voi.png'), width=170*mm, height=66*mm), PageBreak()]

# 7 sensitivity
story += [Paragraph('6. Sensitivity: know what assumption matters', styles['H1x']), Paragraph('The model changes one assumption at a time from low to high while holding other central values fixed. The current pilot indicates the opening-rate range is the strongest driver, followed by seat fill and sector-entry. This tells KSISU which additional evidence is most valuable to improve the decision.', styles['Bodyx']), Image(str(FIG/'sensitivity.png'), width=170*mm, height=66*mm), Spacer(1,4*mm)]
ss=sens.groupby('parameter')['absolute_effect'].mean().sort_values(ascending=False).reset_index(); ss.columns=['Parameter','Mean absolute ratio effect']; ss['Mean absolute ratio effect']=ss['Mean absolute ratio effect'].map(lambda x:f'{x:.3f}')
t=Table([ss.columns.tolist()]+ss.values.tolist(),colWidths=[90*mm,70*mm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#234f7d')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#c8d2df'))]))
story += [t, PageBreak()]

# 8 validation
story += [Paragraph('7. Validation and reproducibility', styles['H1x'])]
c=corr.iloc[0]
s= san.iloc[0]
val=[["Test","Current result","Interpretation"],["District corruption recovery",f"{100*c.matching_recovery_rate:.1f}%",f"Recovered {int(c.matched_unique_districts)}/{int(c.clean_districts)} districts"],["Duplicates removed",str(int(c.duplicates_removed)),"5% duplicate injection test"],["Temporal sanity",f"{float(s.median_abs_share_diff_pct_points):.2f} pp median",s.note],["Randomness",'5,000 shared draws','same draw index across districts'],['Lineage','SHA-256 + source file IDs','reproducible raw-to-output chain']]
t=Table(val,colWidths=[50*mm,45*mm,85*mm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0f2747')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#c8d2df')),('VALIGN',(0,0),(-1,-1),'TOP')]))
story += [t, Spacer(1,6*mm), Paragraph('Important: the temporal Udyam-share check is a consistency test, not an independent ground-truth validation. An independent district total can be supplied through the GUI validation template.', styles['Bodyx']), PageBreak()]

# 9 live demo
story += [Paragraph('8. What the judges see: live user-input GUI', styles['H1x']),
          Paragraph('The interface is designed for a three-minute demonstration. The judge can see the assumptions, swap in a real district-trade file, rerun the identical analysis, and inspect the resulting evidence state.', styles['Bodyx'])]
demo=[['Action','What you say','What changes'],['Run bundled research inputs','"This is the reproducible public-data baseline."','Proxy mode; policy stays NEEDS DATA'],['Show District Priority','"The model tells KSISU where better data matters most."','VOI ranking'],['Load NCVT MIS district-trade export','"Now I replace one proxy with actual district supply."','Supply basis becomes district-actual'],['Rerun','"The uncertainty should shrink because one unknown has been measured."','P10/P90 width changes'],['Open Sensitivity','"We can see which assumption still drives uncertainty."','parameter ranking'],['Open Validation','"Nothing disappears: mismatches and duplicates stay visible."','recovery / duplicate test']]
t=Table(demo,colWidths=[45*mm,70*mm,65*mm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#234f7d')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#c8d2df')),('VALIGN',(0,0),(-1,-1),'TOP')]))
story += [t, Spacer(1,6*mm), Paragraph('User input file shape: <b>district, nco_group_2digit, seats</b> or <b>district, trade, seats</b>. The template is included in `input_templates/`. Use only downloaded/public values in the live demonstration.', styles['Callout']), PageBreak()]

# 10 sources
story += [Paragraph('9. Sources, safeguards and next build', styles['H1x']),
          Paragraph('Primary public sources used or supported by the pipeline:', styles['Bodyx'])]
sources=[
('LGD Download Directory','https://lgdirectory.gov.in/demo/downloadDirectory.do'),
('Udyam district employment OGD resource','https://punjab.data.gov.in/resource/karnataka-udyam-registration-units-employment-details-district-wise-4'),
('ASI Summary Results 2022-23','https://www.mospi.gov.in/sites/default/files/asi_results/ASI%20Summary%20Results%202022-23.pdf'),
('NCVT MIS ITI Count','https://www.ncvtmis.gov.in/pages/iti/count.aspx'),
('NCVT MIS district/trade extract evidence','https://ncvtmis.gov.in/Pages/FileDownload.aspx?fileId=1171'),
('PLFS Annual Report 2022-23','https://www.mospi.gov.in/sites/default/files/publication_reports/AR_PLFS_2022_23N.pdf'),
('Karnataka Udyam 2023-2025 catalog','https://kerala.data.gov.in/catalog/details-karnataka-udyam-registration-2023-2025'),
]
for a,b in sources:
    story.append(Paragraph(f'<b>{a}</b><br/>{b}', styles['Smallx']))
story += [Spacer(1,4*mm), Paragraph('<b>Safeguards:</b> public, aggregated data only; no person-level records; human review before policy use; provenance retained; official-source IDs and checksums recorded; proxy-versus-actual status visible; no official KSI formula claimed.', styles['Bodyx']), Paragraph('<b>AI-use disclosure:</b> AI-assisted research and code generation were used in developing the prototype. All public-source claims used in the submission must be checked against the cited source documents before final filing.', styles['Bodyx']), Paragraph('<b>Next upgrade:</b> load the live LGD export, live NCVT MIS district/trade seats for the two pilot districts, and PLFS occupation-by-industry mix. Then rerun and lock the empirical results.', styles['Callout'])]

doc.build(story)
print(pdf)
