import pandas as pd

from costos.salidas import publicar_bigquery


class TrabajoFalso:
    def result(self):
        return self


class ClienteBigQueryFalso:
    def __init__(self):
        self.cargas = []

    def load_table_from_dataframe(self, tabla, destino, job_config):
        self.cargas.append((destino, len(tabla), job_config.write_disposition))
        return TrabajoFalso()


def test_publica_cada_tabla_reemplazando_su_contenido():
    cliente = ClienteBigQueryFalso()
    publicadas = publicar_bigquery(
        {"pronostico": pd.DataFrame({"a": [1, 2]})}, "proyecto.costos", cliente=cliente
    )
    assert publicadas == ["proyecto.costos.pronostico"]
    assert cliente.cargas == [("proyecto.costos.pronostico", 2, "WRITE_TRUNCATE")]
