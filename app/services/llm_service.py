from langchain_openai import ChatOpenAI
import json
from jinja2 import Template
import logging

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_key: str):
        logger.info("🧠 Initialisation de LLMService avec GPT-4")
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            openai_api_key=api_key
        )
        with open("app/prompts/structured_prompt.txt", "r", encoding="utf-8") as f:
            self.template = Template(f.read())

    def build_prompt(self, user_question: str, dataset: str, schema: list, selected_table: str) -> str:
        """
        Construit un prompt structuré en se basant uniquement sur la table sélectionnée.
        """
        # Filtrer pour ne garder que la table sélectionnée
        table_info = next((t for t in schema if t["name"] == selected_table), None)

        if not table_info:
            raise ValueError(f"La table sélectionnée '{selected_table}' n'a pas été trouvée dans le schéma.")

        # Générer le prompt structuré avec les bonnes variables
        prompt_text = self.template.render(
            prompt=user_question,
            dataset=dataset,
            selected_table=selected_table,
            tables=[table_info]  # Une seule table dans une liste
        )

        #logger.info(f"🧠 Prompt structuré :\n{prompt_text}")
        return prompt_text




    def query(self, structured_prompt: str) -> dict:
        try:
            response = self.llm.invoke(structured_prompt)
            logger.debug(f"🧠 Réponse brute : {response.content!r}")
            result = json.loads(response.content)
            logger.info("✅ Réponse du LLM reçue et parsée")
            return result
        except Exception as e:
            logger.error(f"❌ Erreur dans la requête LLM : {e}")
            raise
