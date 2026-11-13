import json
import pandas as pd
import streamlit as st
from dashboard.repository import ROOT


def render_ml():
    st.subheader('Évaluation des modèles')
    st.caption('Modèles figés entraînés sur 2018–2022 · sélection sur 2023 · test séparé sur 2024.')
    folders=sorted([p for p in (ROOT/'models').glob('*') if p.is_dir() and (p/'manifest.json').exists()],reverse=True)
    if not folders:
        st.info('Aucun modèle entraîné. Dans le terminal, exécuter : python -m ml.train');return
    folder=st.selectbox('Exécution ML',folders,format_func=lambda p:p.name)
    try:
        meta=json.loads((folder/'manifest.json').read_text())
        val=pd.read_csv(folder/'validation.csv')
        st.write('Modèles sélectionnés :',meta['selected'])
        st.caption(f"{meta['training_rows']} lignes d’entraînement · {meta['validation_rows']} de validation · {meta['excluded_label_rows']} lignes exclues pour labels incomplets.")
        st.dataframe(val,hide_index=True,width='stretch')
        st.caption('Log-loss et Brier : plus petits = meilleurs. Average precision et ROC-AUC : plus grands = meilleurs. La baseline prédit la fréquence de la cible dans l’entraînement.')
        st.warning('Les probabilités sont des estimations binaires par pilote, non calibrées après entraînement. Leur somme par course ne vaut pas nécessairement 1 pour la victoire ou 3 pour le podium. Ne pas les interpréter comme des probabilités de course cohérentes à ce stade.')
        test_path=folder/'test.json'
        if test_path.exists():
            report=json.loads(test_path.read_text())
            st.markdown('#### Test final 2024')
            st.dataframe(pd.DataFrame(report['metrics']).T, width='stretch')
            st.caption(f"{report['rows']} observations. Test effectué : {report['evaluated_at']}.")
            csv=folder/'test_predictions.csv'
            if csv.exists():
                st.download_button('Exporter les probabilités rétrospectives 2024',csv.read_bytes(),file_name='test_predictions.csv')
        else:
            st.info(f'Test 2024 non exécuté. Après avoir figé les choix : python -m ml.train --evaluate-test {folder.name}')
        st.caption('Évaluation rétrospective : la liste des participants provient des résultats réels. Les caractéristiques utilisent les seules courses antérieures, mais les corrections historiques de la source ne sont pas des archives telles que connues le jour de la course. Le modèle ne constitue pas encore une prédiction opérationnelle d’un prochain GP.')
    except (OSError,ValueError,KeyError):
        st.error('Rapport ML incomplet ou invalide. Vérifier que l’entraînement s’est terminé.')
