import pandas as pd
import plotly.express as px
import streamlit as st
from dashboard.comparison import subset,summary,race_duel,qualifying_duel,points_by_round


def render_comparison(data,rd):
    st.subheader('Comparer les performances')
    st.caption(f'Saison sélectionnée · jusqu’à la manche {rd} incluse. Les filtres de ce comparateur sont indépendants du filtre d’écuries des résultats.')
    kind=st.radio('Comparer', ['Pilotes','Écuries'],horizontal=True,key='comparison_kind')
    entity,label=('driver_id','driver') if kind=='Pilotes' else ('constructor_id','constructor')
    results=data['results'].loc[data['results']['round']<=rd]
    options=results[[entity,label]].drop_duplicates(entity).sort_values(label)
    if len(options)<2:
        st.info('Il faut au moins deux entités avec des résultats pour effectuer une comparaison.'); return
    names=dict(zip(options[entity],options[label]))
    ids=options[entity].tolist()
    a=st.selectbox('Première sélection',ids,format_func=names.get,key=f'{entity}_a')
    others=[x for x in ids if x!=a]
    b=st.selectbox('Deuxième sélection',others,format_func=names.get,key=f'{entity}_b')
    mode=st.radio('Périmètre',['Toutes leurs courses','Courses communes'],horizontal=True,key='comparison_scope')
    left=subset(data['results'],entity,a,rd);right=subset(data['results'],entity,b,rd)
    shared=set(left['round'])&set(right['round'])
    allowed=shared if mode=='Courses communes' else None
    if allowed is not None:
        left=left.loc[left['round'].isin(allowed)];right=right.loc[right['round'].isin(allowed)]
    st.caption(f'{len(shared)} manche(s) avec un résultat pour les deux sélections. Les absences ne sont pas converties en zéro.')
    if left.empty and right.empty:
        st.info('Aucune course commune dans le périmètre sélectionné.');return
    def selected(frame,ident):
        out=subset(frame,entity,ident,rd)
        return out.loc[out['round'].isin(allowed)] if allowed is not None else out
    sa=summary(left,selected(data['sprint_results'],a))
    sb=summary(right,selected(data['sprint_results'],b))
    measures=pd.DataFrame({'Indicateur':list(sa),names[a]:list(sa.values()),names[b]:list(sb.values())})
    st.dataframe(measures,hide_index=True,width='stretch')
    st.caption('Victoires et podiums : nombres de résultats de pilotes en GP. Position moyenne : moyenne des positions connues, tous statuts confondus ; pour une écurie, elle regroupe ses pilotes. Points absents : total laissé vide. Aucun sprint connu : total sprint laissé vide.')
    st.caption('Les points ci-dessus sont ceux des résultats GP et sprint, séparément. Des sanctions peuvent créer un écart avec le classement officiel de l’onglet Championnat.')
    if kind=='Pilotes':
        duel=race_duel(left,right)
        st.markdown('#### Face-à-face en course')
        cols=st.columns(3)
        cols[0].metric(f'{names[a]} devant',duel['a'])
        cols[1].metric(f'{names[b]} devant',duel['b'])
        cols[2].metric('Manches comparables',duel['total'])
        st.caption(f"Positions officielles connues pour les deux pilotes seulement ; tous statuts confondus. Égalités : {duel['ties']}.")
    chart=points_by_round(left,right,names[a],names[b])
    if not chart.empty:
        st.plotly_chart(px.bar(chart,x='Manche',y='Points GP',color='Entité',barmode='group',
            title='Points par Grand Prix · hors sprints'),width='stretch')
    st.markdown('#### Face-à-face en qualifications')
    session=st.radio('Séance à comparer',['Q1','Q2','Q3'],horizontal=True,key='duel_session')
    qa=selected(data['qualifying'],a);qb=selected(data['qualifying'],b)
    paired=qualifying_duel(qa,qb,session)
    if paired.empty:
        st.info('Aucun temps connu pour les deux sélections dans la même séance et la même manche.')
    else:
        delta=paired['delta_seconds']
        cols=st.columns(3)
        cols[0].metric(f'{names[a]} plus rapide',int((delta<0).sum()))
        cols[1].metric(f'{names[b]} plus rapide',int((delta>0).sum()))
        cols[2].metric('Écart moyen A − B',f'{delta.mean():+.3f} s')
        st.caption(f'{len(paired)} séance(s) comparable(s). Écart négatif : première sélection plus rapide. Pour une écurie, meilleur temps connu de ses pilotes ; une donnée absente peut donc limiter la comparaison.')
        view=paired.rename(columns={'round':'Manche',session.lower()+'_seconds_a':names[a]+' (s)',
            session.lower()+'_seconds_b':names[b]+' (s)','delta_seconds':'Écart A − B (s)'})
        st.dataframe(view,hide_index=True,width='stretch')
    st.download_button('Exporter la comparaison CSV',measures.to_csv(index=False).encode('utf-8-sig'),
                       file_name=f'comparaison_{a}_{b}_manche_{rd}.csv',mime='text/csv')
