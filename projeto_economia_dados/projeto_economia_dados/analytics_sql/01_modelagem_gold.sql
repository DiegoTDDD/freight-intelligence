CREATE OR REPLACE VIEW vw_gold_macroeconomia AS
WITH BaseMonetaria_CTE AS (
    SELECT 
        data,
        base_monetaria_milhoes,
        LAG(base_monetaria_milhoes, 12) OVER(ORDER BY data) as m2_12m_atras
    FROM base_monetaria
),
Calculo_Expansao AS (
    SELECT 
        data,
        base_monetaria_milhoes,
        ROUND(((base_monetaria_milhoes - m2_12m_atras) / m2_12m_atras * 100)::numeric, 2) AS expansao_m2_yoy_pct
    FROM BaseMonetaria_CTE
)
SELECT 
    c.data,
    c.base_monetaria_milhoes,
    c.expansao_m2_yoy_pct,
    i.ipca_mensal
FROM Calculo_Expansao c
INNER JOIN ipca i ON c.data = i.data
WHERE c.expansao_m2_yoy_pct IS NOT NULL
ORDER BY c.data DESC;
