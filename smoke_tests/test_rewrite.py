from src.api.llm import rewrite_query

# Test 1 — cronologia vuota: deve tornare query invariata
result = rewrite_query([], "How are my holidays calculated?")
print("Test 1:", result)

# Test 2 — follow-up contestuale
history = [
    ("quanto prendo di bonus natalizio?",
     "The holiday bonus is 8.33% of annual gross salary. On €14.71/hour it is approximately €135 gross.")
]
result = rewrite_query(history, "and how much is that net?")
print("Test 2:", result)

# Test 3 — follow-up inferenziale (il caso critico)
history = [
    ("ho lavorato 7 mesi, in che fase sono?",
     "After 7 months you are in Phase B of the Adecco contract.")
]
result = rewrite_query(history, "and if I get sick now?")
print("Test 3:", result)

# Test 4 — cambio di argomento: NON deve iniettare contesto precedente
history = [
    ("What is the minimum wage?",
     "The minimum wage in 2026 is €14.06 per hour.")
]
result = rewrite_query(history, "how do I reset my Uber Eats app?")
print("Test 4:", result)

# Test 5 — input in arabo (rischio linguistico: l'output deve essere in inglese)
history = [
    ("كم مبلغ مكافأة الإجازة؟",
     "مكافأة الإجازة هي 8.33٪ من الراتب السنوي الإجمالي.")
]
result = rewrite_query(history, "what is the net amount?")
print("Test 5:", result)