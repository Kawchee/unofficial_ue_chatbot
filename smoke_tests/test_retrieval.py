from src.retrieval.retriever import search

queries = [
    "What happens if I don't reactivate my account?",
    "What should I do if I am sick and cannot work?",
    "What are metrics and how do they work?",
    "How much will I earn per hour?",
    "How much is my net earnings on the bonus?",
    "Who can I contact for payment issues?",
    "What documents do I need to start working?",
    "If a restaurant is closed, can the customer cancel the order?",
    "If a restaurant is closed and I have Uber Eats support cancel my order, will this impact my metrics?",
    "How long does Uber Eats say I must wait between shifts?",
    "I finished a shift at 9:00 PM, Uber made me work until half an hour later, then I tried to reconnect for the next shift but it told me my driving hours were limited and I couldn't finish the second shift. Ridiculous. But why?",
]

for query in queries:
    print(f"\n{'=' * 60}")
    print(f"QUERY: {query}")
    print("=" * 60)
    results = search(query, top_k=3)
    for i, chunk in enumerate(results):
        print(f"[{i+1}] {chunk['metadata']['file_name']}")
        print(f"     Sezione: {chunk['metadata']['section_title'][:70]}")
        print(f"     Score:   {chunk['rerank_score']:.4f}")
        print(f"     Estratto: {chunk['content'][:150]}")
        print()