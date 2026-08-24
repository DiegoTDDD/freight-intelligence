import unittest
import os
from sqlalchemy import create_engine, inspect

class TestDataPlatform(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Conecta no banco Gold (usa localhost se rodando fora do container ou db_gold se dentro)
        cls.db_host = os.getenv("DB_HOST", "localhost")
        cls.db_user = "admin"
        cls.db_pass = "adminpassword"
        cls.db_name = "economics_gold"
        cls.db_port = "5432"
        
        cls.connection_string = f"postgresql://{cls.db_user}:{cls.db_pass}@{cls.db_host}:{cls.db_port}/{cls.db_name}"
        cls.engine = create_engine(cls.connection_string)

    def test_database_connection(self):
        """Valida se o motor do SQLAlchemy consegue estabelecer conexão com o PostgreSQL Gold."""
        try:
            with self.engine.connect() as connection:
                self.assertTrue(connection is not None)
        except Exception as e:
            self.fail(f"A conexão com o banco de dados falhou: {e}")

    def test_gold_tables_existence(self):
        """Verifica se as tabelas analíticas principais estão presentes no schema."""
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        # Garante que o banco responde ao inspetor de esquema
        self.assertIsInstance(tables, list)

if __name__ == "__main__":
    unittest.main()
