from google.cloud import bigquery
import os
import json
import logging

logger = logging.getLogger(__name__)

class BigQueryService:
    def __init__(self, credentials: dict):
        logger.info("🔐 Initialisation de BigQueryService")
        self.credentials_path = "temp_credentials.json"

        try:
            with open(self.credentials_path, "w") as f:
                json.dump(credentials, f)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
            self.client = bigquery.Client()
            logger.info("✅ Client BigQuery initialisé avec succès")
        except Exception as e:
            logger.error(f"❌ Échec de l'initialisation du client BigQuery : {e}")
            raise

    def get_datasets(self):
        try:
            datasets = [d.dataset_id for d in self.client.list_datasets()]
            logger.info(f"📁 Datasets trouvés : {datasets}")
            return datasets
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des datasets : {e}")
            raise

    def get_tables(self, dataset):
        try:
            tables = [t.table_id for t in self.client.list_tables(dataset)]
           # logger.info(f"📄 Tables pour le dataset {dataset} : {tables}")
            return tables
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des tables : {e}")
            raise

    def describe_schema(self, dataset):
        try:
            schema = []
            for table in self.get_tables(dataset):
                table_ref = self.client.get_table(f"{dataset}.{table}")
                schema.append({
                    "name": table,
                    "columns": [
                        {"name": field.name, "type": field.field_type}
                        for field in table_ref.schema
                    ]
                })
            logger.info(f"📚 Schéma du dataset {dataset} récupéré avec succès")
            return schema
        except Exception as e:
            logger.error(f"❌ Erreur lors de la description du schéma : {e}")
            raise

    def run_query(self, query: str):
        try:
            logger.info(f"\n\n🚀 Exécution de la requête SQL")
            df = self.client.query(query).to_dataframe()
            logger.info(f"✅ Requête exécutée avec succès, {len(df)} lignes retournées")
            return df
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'exécution de la requête : {e}")
            raise
