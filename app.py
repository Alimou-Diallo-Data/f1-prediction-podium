import pandas as pd
import plotly.express as px
import streamlit as st
from dashboard.repository import load_snapshot, DatabaseUnavailable
from dashboard.analytics import season_data, standings_at, qualifying_gap

st.set_page_config(page_title='F1 • Tableau de bord',page_icon='🏁',layout='wide')
st.title('🏁 F1 · Tableau de bord')
st.caption('Résultats historiques · Classements officiels · Qualifications')

@st.cache_data(ttl=300,show_spinner='Lecture de PostgreSQL…')
def cached_data():
    return load_snapshot()

if st.sidebar.button('Actualiser les données'):
    cached_data.clear()
try:
    data=cached_data()
except DatabaseUnavailable as exc:
    st.error(str(exc)); st.stop()
if data['races'].empty:
    st.info('Aucune course chargée. Exécuter le pipeline ETL avant de consulter le dashboard.'); st.stop()
season=st.sidebar.selectbox('Saison',sorted(data['races']['season'].unique(),reverse=True))
d=season_data(data,season)
races=d['races'].sort_values('round')
completed=d['results']['round']
default_round=int(completed.max()) if not completed.empty else int(races['round'].max())
rounds=races['round'].tolist()
rd=st.sidebar.selectbox('Grand Prix',rounds,index=rounds.index(default_round),
    format_func=lambda r:f"{r} · {races.loc[races['round']==r,'name'].iloc[0]}")
race=races.loc[races['round']==rd].iloc[0]
st.subheader(f"{race['name']} · {season}")
st.write(f"{race['circuit']} — {race['country']} · {race['race_date']}")
metrics=st.columns(4)
for col,label,value in zip(metrics,['Courses au calendrier','Courses avec résultats','Pilotes en course','Écuries en course'],
    [len(races),d['results']['round'].nunique(),d['results']['driver_id'].nunique(),d['results']['constructor_id'].nunique()]):
    col.metric(label,int(value))
st.caption('Les indicateurs ci-dessus concernent la saison entière.')
if not d['runs'].empty:
    st.sidebar.caption(f"Dernier ETL réussi : {d['runs']['finished_at'].iloc[0]}")
st.sidebar.caption('Lecture seule · Cache 5 minutes. Actualiser relit la base sans appeler Jolpica.')

labels={'position':'Position','driver':'Pilote','constructor':'Écurie','points':'Points',
        'grid':'Grille','laps':'Tours','status':'Statut','wins':'Victoires','round':'Manche'}
def table(df,columns):
    shown=df[columns].rename(columns=labels)
    st.dataframe(shown,hide_index=True,width='stretch')
    return shown

tabs=st.tabs(['Résultats','Championnat','Qualifications','Calendrier','Comparateurs','Machine Learning','Explications SHAP'])
with tabs[0]:
    result=d['results'].loc[d['results']['round']==rd]
    if result.empty:
        st.info('Résultats indisponibles pour ce Grand Prix.')
    else:
        podium=result.loc[result['position'].isin([1,2,3])]
        for col,pos in zip(st.columns(3),[1,2,3]):
            driver=podium.loc[podium['position']==pos,'driver']
            col.metric(f'P{pos}',driver.iloc[0] if len(driver)==1 else 'Indisponible')
        teams=sorted(result['constructor'].unique())
        selected=st.multiselect('Filtrer les écuries',teams)
        visible=result.loc[result['constructor'].isin(selected)] if selected else result
        displayed=table(visible,['position','driver','constructor','grid','points','laps','status'])
        st.download_button('Télécharger les résultats CSV',displayed.to_csv(index=False).encode('utf-8-sig'),
                           file_name=f'resultats_{season}_{rd}.csv',mime='text/csv')
        st.caption('Grille 0 : valeur fournie par la source, pas une pole position. Valeur absente : inconnue.')
    sprint=d['sprint_results'].loc[d['sprint_results']['round']==rd]
    if not sprint.empty:
        st.markdown('### Sprint')
        table(sprint,['position','driver','constructor','points','status'])
with tabs[1]:
    for name,entity,title in [('driver_standings','driver','Pilotes'),('constructor_standings','constructor','Écuries')]:
        st.markdown(f'### {title}')
        ranking,actual=standings_at(d[name],rd)
        if ranking.empty:
            st.info('Classement indisponible avant ou après cette manche dans les données chargées.'); continue
        st.caption(f'Classement officiel après la manche {actual}'+(' — dernière manche disponible avant la sélection.' if actual!=rd else '.'))
        table(ranking,['position',entity,'points','wins'])
        chart=ranking.head(10).copy()
        chart['points']=pd.to_numeric(chart['points'],errors='coerce')
        st.plotly_chart(px.bar(chart,x=entity,y='points',labels={entity:title,'points':'Points'},
            title=f'Top 10 · après la manche {actual}'),width='stretch')
        defaults=ranking[entity].head(3).tolist()
        chosen=st.multiselect(f'Évolution des points — {title}',sorted(d[name][entity].unique()),default=defaults,key=name)
        evolution=d[name].loc[(d[name]['round']<=rd)&d[name][entity].isin(chosen)].copy()
        if not evolution.empty:
            evolution['points']=pd.to_numeric(evolution['points'],errors='coerce')
            st.plotly_chart(px.line(evolution,x='round',y='points',color=entity,markers=True,
                labels={'round':'Manche','points':'Points',entity:title}),width='stretch')
    st.caption('Points issus des classements officiels ; ils ne sont pas recalculés à partir des seuls résultats de course.')
with tabs[2]:
    quali=d['qualifying'].loc[d['qualifying']['round']==rd]
    if quali.empty:
        st.info('Qualifications indisponibles pour ce Grand Prix.')
    else:
        q=qualifying_gap(quali)
        session=st.radio('Séance',['Q1','Q2','Q3'],horizontal=True)
        prefix=session.lower()
        cols=['position','driver','constructor',f'{prefix}_seconds',f'{prefix}_gap']
        view=q[cols].rename(columns={**labels,f'{prefix}_seconds':f'{session} (secondes)',f'{prefix}_gap':'Écart au meilleur (s)'})
        st.dataframe(view,hide_index=True,width='stretch')
        st.caption('Chaque écart utilise le meilleur temps de la séance sélectionnée. Les absences restent vides. La position est celle du classement global des qualifications.')
with tabs[3]:
    calendar=races.copy()
    calendar['Résultats disponibles']=calendar['round'].isin(completed)
    st.dataframe(calendar[['round','name','race_date','circuit','country','Résultats disponibles']].rename(
        columns={'round':'Manche','name':'Grand Prix','race_date':'Date','circuit':'Circuit','country':'Pays'}),
        hide_index=True,width='stretch')
with tabs[4]:
    from dashboard.comparison_ui import render_comparison
    render_comparison(d,rd)
with tabs[5]:
    from dashboard.ml_ui import render_ml
    render_ml()
with tabs[6]:
    from dashboard.shap_ui import render_shap
    render_shap(data)
st.caption('Source : Jolpica via le pipeline ETL. Les prédictions seront ajoutées après entraînement et évaluation des modèles.')
