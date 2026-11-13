import json
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from ml.features import FEATURES
from ml.train import dataset,digest
from ml.explain import LABELS,explain_row,training_background,load_local_model,baseline_report
from dashboard.repository import ROOT

@st.cache_data(show_spinner='Reconstruction des variables historiques…',ttl=300)
def reconstructed(data):
    return dataset(data,2024)

@st.cache_data(show_spinner='Calcul des contributions SHAP…',max_entries=32)
def cached_explanation(folder,target,model_stamp,background,row):
    model=load_local_model(Path(folder),target)
    return explain_row(model,background,row)


def render_shap(data):
    st.subheader('Pourquoi cette estimation ?')
    st.caption('Explications des modèles S5 figés · relecture historique 2023/2024 · avant qualifications.')
    folders=sorted([p for p in (ROOT/'models').glob('*') if p.is_dir() and (p/'manifest.json').exists()],reverse=True)
    if not folders:
        st.info('Copier le dossier models de S5 dans ce projet pour retrouver les modèles déjà entraînés.');return
    folder=st.selectbox('Modèles à expliquer',folders,format_func=lambda p:p.name,key='shap_run')
    try:
        meta=json.loads((folder/'manifest.json').read_text())
        development=pd.read_csv(folder/'features_development.csv')
        if (folder/'test_predictions.csv').exists():
            with st.expander('Baseline sur 2024 — comparaison complémentaire'):
                baseline=baseline_report(development,pd.read_csv(folder/'test_predictions.csv'))
                st.dataframe(baseline,hide_index=True,width='stretch')
                st.caption('Fréquences apprises sur 2018–2022 et appliquées aux mêmes observations test. Les scores et modèles S5 restent inchangés ; cette analyse ne sert pas à les sélectionner à nouveau.')
        frame=reconstructed(data)
        if digest(dataset(data,2023))!=meta['feature_sha256']:
            st.error('Les données historiques ont changé depuis S5. Les explications sont bloquées pour éviter de mélanger les versions.');return
        history=pd.concat([development.loc[development.season==2023],frame.loc[frame.season==2024]],ignore_index=True)
        valid=history.dropna(subset=['win','podium'])
        if valid.empty:
            st.info('Aucune course éligible en 2023 ou 2024.');return
        year=st.selectbox('Année à expliquer',sorted(valid.season.unique(),reverse=True),key='shap_year')
        available=valid.loc[valid.season==year]
        names=data['races'].loc[data['races'].season==year].set_index('round')['name'].to_dict()
        rd=st.selectbox('Course à expliquer',sorted(available['round'].unique()),
                        format_func=lambda v:f'{v} · {names.get(v,"Grand Prix")}',key='shap_round')
        entrants=available.loc[available['round']==rd]
        driver_names=data['results'].drop_duplicates('driver_id').set_index('driver_id')['driver'].to_dict()
        driver=st.selectbox('Pilote à expliquer',sorted(entrants.driver_id),format_func=lambda v:driver_names.get(v,v),key='shap_driver')
        target=st.selectbox('Probabilité à expliquer',['win','podium'],format_func=lambda v:'Victoire' if v=='win' else 'Podium',key='shap_target')
        row=entrants.loc[entrants.driver_id==driver,FEATURES]
        saved=None
        if year==2024:
            test_file=folder/'test_predictions.csv'
            if not test_file.exists():
                st.info('Test 2024 absent. Exécuter la commande de test séparé affichée dans Machine Learning.');return
            saved=pd.read_csv(test_file)
            saved=saved.loc[(saved['round']==rd)&(saved.driver_id==driver)]
            if len(saved)!=1:
                st.error('Observation absente du test sauvegardé.');return
        st.caption(f"Modèle : {meta['selected'][target]}. Le premier calcul peut prendre plusieurs secondes.")
        key=f'{folder.name}|{year}|{rd}|{driver}|{target}'
        if st.button('Expliquer cette estimation',key='explain_button'):
            stamp=(folder/f'{target}.joblib').stat().st_mtime_ns
            result=cached_explanation(str(folder),target,stamp,training_background(development),row)
            if saved is not None and abs(result['probability']-float(saved.iloc[0][f'p_{target}']))>1e-6:
                st.error('La probabilité diffère du test sauvegardé. Vérifier les données et la version du modèle.');return
            st.session_state['shap_result']=(key,result)
        stored=st.session_state.get('shap_result')
        if not stored or stored[0]!=key: return
        result=stored[1]
        cols=st.columns(2)
        cols[0].metric('Probabilité estimée',f"{100*result['probability']:.2f} %")
        cols[1].metric('Référence du modèle',f"{100*result['base']:.2f} %")
        display=pd.DataFrame({'Variable':[LABELS.get(f,f) for f in FEATURES],
                              'Contribution (points de %)':[100*v for v in result['contributions']]})
        display['Sens']=display['Contribution (points de %)'].map(lambda v:'Augmente' if v>0 else ('Diminue' if v<0 else 'Neutre'))
        st.plotly_chart(px.bar(display.sort_values('Contribution (points de %)'),x='Contribution (points de %)',y='Variable',color='Sens',orientation='h',
            color_discrete_map={'Augmente':'#ef5350','Diminue':'#42a5f5','Neutre':'#9e9e9e'},
            title='Contributions par rapport à la référence',height=550),width='stretch')
        st.caption('Référence + somme des contributions = probabilité estimée. +5 points fait passer, par exemple, de 10 % à 15 %. SHAP explique le modèle et ne démontre aucun effet causal.')
        st.dataframe(display,hide_index=True,width='stretch')
        details=row.T.reset_index();details.columns=['Variable','Valeur utilisée']
        details['Variable']=details.Variable.map(LABELS)
        details['Valeur utilisée']=details['Valeur utilisée'].map(lambda v:'Inconnue' if pd.isna(v) else str(v))
        with st.expander('Données et méthode de calcul'):
            st.dataframe(details,hide_index=True,width='stretch')
            st.write(f"SHAP par permutation · {result['background_size']} observations d’entraînement de référence · budget {result['max_evals']} · graine {result['seed']}.")
            st.caption(f"Résidu d’additivité : {result['residual']:.2e}. Les variables corrélées peuvent partager leurs contributions ; le masquage indépendant peut produire des combinaisons rares de pilote, écurie et historique.")
        export={'run':folder.name,'season':int(year),'round':int(rd),'driver_id':driver,'target':target,**result}
        st.download_button('Exporter l’explication JSON',json.dumps(export,indent=2),file_name=f'shap_{year}_{rd}_{driver}_{target}.json',mime='application/json')
    except ImportError:
        st.error('Dépendance SHAP absente ou incompatible. Installer requirements.txt dans l’environnement Linux actif.')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        st.error(f'Explication indisponible : {exc}')
