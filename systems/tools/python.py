from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL

python_repl = PythonREPL()


@tool
def python_calculator_tool(code: str) -> str:
    """Exécute du code Python pour un calcul ou une statistique.

    Le résultat doit être affiché avec print() pour être renvoyé.
    """
    try:
        result = python_repl.run(code)
        return f"Résultat Python :\n{result}"
    except Exception as e:
        return f"Erreur Python : {str(e)}"
