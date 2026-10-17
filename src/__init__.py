"""Motor determinístico do fechamento Tarvo (python -m src)."""
import pandas as pd

# pandas 3 passa a inferir texto como dtype "str" (vazio = NaN); pandas 2 usa object (vazio = None).
# Para pandas 2 e 3 gerarem o mesmo saida/, byte a byte, o motor fixa o comportamento object/None.
try:
    pd.set_option("future.infer_string", False)
except pd.errors.OptionError:   # pandas antigo, sem a opção: já se comporta assim
    pass
