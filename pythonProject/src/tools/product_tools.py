"""Product search capability backed by an explicit repository."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from harness.errors import DependencyUnavailableError


class ProductSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insurance_type: str | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    occupation: str | None = None
    budget: float | None = Field(default=None, ge=0)
    product_name_like: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class Product(BaseModel):
    model_config = ConfigDict(extra="allow")

    product_id: str
    product_name: str
    insurance_type: str
    min_age: int | None = None
    max_age: int | None = None
    min_price: float | None = None
    max_price: float | None = None
    target_occupations: str = ""
    description: str = ""
    is_active: bool = True


class ProductRepository(Protocol):
    def search_active(self, query: ProductSearchInput) -> list[dict[str, Any]]: ...


class MySQLProductRepository:
    """SQL repository that can never return inactive products."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def search_active(self, query: ProductSearchInput) -> list[dict[str, Any]]:
        connection = None
        cursor = None
        try:
            connection = self.client.connect()
            import pymysql

            cursor = connection.cursor(pymysql.cursors.DictCursor)
            conditions = ["is_active=1"]
            params: list[Any] = []
            if query.insurance_type:
                conditions.append("insurance_type = %s")
                params.append(query.insurance_type)
            if query.age is not None:
                conditions.append("min_age <= %s AND max_age >= %s")
                params.extend((query.age, query.age))
            if query.budget is not None:
                conditions.append("min_price <= %s")
                params.append(query.budget)
            if query.occupation:
                conditions.append(
                    "(target_occupations LIKE %s OR target_occupations LIKE %s)"
                )
                params.extend((f"%{query.occupation}%", "%全部职业%"))
            if query.product_name_like:
                conditions.append("product_name LIKE %s")
                params.append(f"%{query.product_name_like}%")
            params.append(query.limit)
            sql = (
                "SELECT product_id, product_name, insurance_type, min_age, max_age, "
                "min_price, max_price, target_occupations, description, is_active "
                f"FROM insurance_products WHERE {' AND '.join(conditions)} "
                "ORDER BY min_price ASC LIMIT %s"
            )
            cursor.execute(sql, params)
            rows = list(cursor.fetchall())
            for row in rows:
                for field in ("min_price", "max_price"):
                    if row.get(field) is not None:
                        row[field] = float(row[field])
            return rows
        except DependencyUnavailableError:
            raise
        except Exception as exc:
            raise DependencyUnavailableError(
                "MySQL product repository is unavailable",
                details={"dependency": "mysql"},
                retryable=True,
            ) from exc
        finally:
            if cursor is not None:
                cursor.close()
            # Connections are owned and finally closed by the lifespan client.


class FakeProductRepository:
    """Explicit test/demo adapter; never enabled implicitly."""

    def __init__(self, products: list[dict[str, Any]]) -> None:
        self.products = products

    def search_active(self, query: ProductSearchInput) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        for product in self.products:
            if not bool(product.get("is_active", 1)):
                continue
            if query.insurance_type and product.get("insurance_type") != query.insurance_type:
                continue
            if query.age is not None and not (
                int(product.get("min_age", 0)) <= query.age <= int(product.get("max_age", 120))
            ):
                continue
            if query.budget is not None and float(product.get("min_price", 0)) > query.budget:
                continue
            occupations = str(product.get("target_occupations", ""))
            if query.occupation and query.occupation not in occupations and "全部职业" not in occupations:
                continue
            if query.product_name_like and query.product_name_like not in str(product.get("product_name", "")):
                continue
            matched.append(dict(product))
        return matched[: query.limit]
