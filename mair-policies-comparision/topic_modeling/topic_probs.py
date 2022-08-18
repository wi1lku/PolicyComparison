from typing import Dict, List, Tuple, Union
import warnings

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as hc
import scipy.spatial as sp
from gensim.corpora.dictionary import Dictionary
from gensim.models import LdaModel
from sklearn.manifold import TSNE


def get_topic_probs(
    df: pd.DataFrame,
    filter_dict: Dict[str, str],
    model: LdaModel,
    num_topics: int,
    encoded_docs: pd.Series,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    corpus_model = model[encoded_docs]
    df_metainfo = df.loc[(df[list(filter_dict)] == pd.Series(filter_dict)).all(axis=1)]
    res_len = len(df_metainfo)
    res = np.zeros((res_len, num_topics))
    for i, doc in enumerate(corpus_model):
        for topic in doc:
            res[i][topic[0]] = np.round(topic[1], 4)
    modeling_results = pd.concat([df_metainfo.reset_index(drop=True), pd.DataFrame(res)], axis=1)
    topic_probs = modeling_results.groupby("country").mean().loc[:, np.arange(num_topics)]

    return modeling_results, topic_probs


def calculate_linkage_matrix(
    topic_probs: pd.DataFrame, method: str = "average", metric: str = "cosine"
) -> np.ndarray:
    return hc.linkage(topic_probs, method=method, metric=metric)


def calculate_distance_matrix(topic_probs: pd.DataFrame, metric: str = "hd") -> pd.DataFrame:
    if metric == "ir":
        metric = lambda p, q: np.sum(p * np.log(2 * p / (p + q))) + np.sum(
            q * np.log(2 * q / (p + q))
        )
    if metric == "hd":
        metric = lambda p, q: np.sqrt(np.sum((np.sqrt(p) - np.sqrt(q)) ** 2)) / np.sqrt(2)
    distances = sp.distance.squareform(sp.distance.pdist(topic_probs.values, metric=metric))
    return pd.DataFrame(distances, index=topic_probs.index, columns=topic_probs.index)


def get_similarities(topic_probs: pd.DataFrame) -> np.ndarray:
    return sp.distance.squareform(sp.distance.pdist(topic_probs.values, metric="cosine"))


def shift_similarity(
    modeling_results: pd.DataFrame,
    num_topics: int,
    filter_dicts: List[Dict[str, str]],
    ir_delta: int = 1,
) -> pd.DataFrame:
    countries = modeling_results.country.unique()
    assert len(filter_dicts) == 2
    dimension_change = {"country": [], "cosine_sim": [], "IR_sim": [], "H_sim": []}
    for country in countries:
        df1 = modeling_results.loc[
            (modeling_results["country"] == country)
            & (modeling_results[list(filter_dicts[0])] == pd.Series(filter_dicts[0])).all(axis=1)
        ].loc[:, np.arange(num_topics)]
        df2 = modeling_results.loc[
            (modeling_results["country"] == country)
            & (modeling_results[list(filter_dicts[1])] == pd.Series(filter_dicts[1])).all(axis=1)
        ].loc[:, np.arange(num_topics)]
        if df1.shape[0] == 1:
            dimension_change["country"].append(country)
            dimension_change["cosine_sim"].append(1 - sp.distance.cosine(df1, df2))
            p = df1.values
            q = df2.values
            ir = np.sum(p * np.log(2 * p / (p + q))) + np.sum(q * np.log(2 * q / (p + q)))
            dimension_change["IR_sim"].append(10 ** (-ir_delta * ir))
            dimension_change["H_sim"].append(
                1 - (np.sqrt(np.sum((np.sqrt(p) - np.sqrt(q)) ** 2)) / np.sqrt(2))
            )
    return pd.DataFrame(dimension_change)


def topic_probs_by_column_binded(
    modeling_results: pd.DataFrame, num_topics: int, column: str = "country"
) -> pd.DataFrame:
    result = []
    column_vals_added = []
    column_vals = modeling_results.country.unique()
    rows_by_column = modeling_results.groupby(column).count()[0].max()
    for column_val in column_vals:
        df_tmp = modeling_results[modeling_results[column] == column_val]
        if df_tmp.shape[0] != rows_by_column:
            warnings.warn(f"{column} - {column_val} has missing rows!")
            continue
        result.append(df_tmp.iloc[:, -num_topics:].values.flatten())
        column_vals_added.append(column_val)
    res = pd.DataFrame(np.vstack(result), index=column_vals_added)
    res.index.name = column
    return res


def tsne_dim_reduction(
    result_df: pd.DataFrame,
    num_topics: int,
    random_state: int = 42,
    perplexity: int = 40,
    n_iter: int = 1000,
    init: str = "pca",
    learning_rate: Union[str, float] = "auto",
) -> pd.DataFrame:
    tsne_result_df = result_df.copy()
    tsne = TSNE(
        n_components=2,
        verbose=1,
        perplexity=perplexity,
        n_iter=n_iter,
        init=init,
        learning_rate=learning_rate,
        random_state=random_state,
    )
    tsne_raw_result = tsne.fit_transform(result_df.iloc[:, -num_topics:])
    tsne_result_df["c1"] = tsne_raw_result[:, 0]
    tsne_result_df["c2"] = tsne_raw_result[:, 1]
    return tsne_result_df


def get_hierarchical_clusters(linkage: np.ndarray, t: float = 1.0):
    return hc.fcluster(linkage, t=t)
