CREATE TABLE customers (
  customer_id SERIAL PRIMARY KEY,
  full_name TEXT NOT NULL,
  city TEXT NOT NULL,
  country TEXT NOT NULL,
  segment TEXT NOT NULL,
  created_at DATE NOT NULL
);

CREATE TABLE products (
  product_id SERIAL PRIMARY KEY,
  product_name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit_price NUMERIC(10,2) NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE orders (
  order_id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(customer_id),
  order_date DATE NOT NULL,
  status TEXT NOT NULL,
  sales_channel TEXT NOT NULL
);

CREATE TABLE order_items (
  order_item_id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(order_id),
  product_id INT NOT NULL REFERENCES products(product_id),
  quantity INT NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(10,2) NOT NULL
);

INSERT INTO customers (full_name, city, country, segment, created_at) VALUES
  ('Anna Schmidt', 'Berlin', 'Germany', 'SMB', '2024-01-10'),
  ('Luca Rossi', 'Milan', 'Italy', 'Enterprise', '2024-02-05'),
  ('Maya Patel', 'London', 'United Kingdom', 'SMB', '2024-03-18'),
  ('Noah Johnson', 'Austin', 'United States', 'Startup', '2024-04-22'),
  ('Sofia Garcia', 'Madrid', 'Spain', 'Enterprise', '2024-05-14'),
  ('Emil Novak', 'Prague', 'Czech Republic', 'Startup', '2024-06-01');

INSERT INTO products (product_name, category, unit_price, active) VALUES
  ('AI Starter Pack', 'Software', 49.00, TRUE),
  ('Team Analytics Suite', 'Software', 199.00, TRUE),
  ('Vision API Credits', 'Usage', 79.00, TRUE),
  ('Voice Bot Minutes', 'Usage', 59.00, TRUE),
  ('Prompt Engineering Workshop', 'Services', 899.00, TRUE),
  ('Legacy Reporting Add-on', 'Software', 29.00, FALSE);

INSERT INTO orders (customer_id, order_date, status, sales_channel) VALUES
  (1, '2025-01-12', 'paid', 'website'),
  (2, '2025-01-19', 'paid', 'sales'),
  (3, '2025-02-03', 'paid', 'website'),
  (4, '2025-02-17', 'pending', 'partner'),
  (5, '2025-03-01', 'paid', 'sales'),
  (1, '2025-03-11', 'paid', 'website'),
  (6, '2025-03-19', 'cancelled', 'website'),
  (2, '2025-04-02', 'paid', 'sales');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
  (1, 1, 2, 49.00),
  (1, 3, 1, 79.00),
  (2, 2, 3, 199.00),
  (2, 5, 1, 899.00),
  (3, 1, 5, 49.00),
  (3, 4, 2, 59.00),
  (4, 2, 1, 199.00),
  (5, 2, 2, 199.00),
  (5, 3, 4, 79.00),
  (6, 4, 10, 59.00),
  (6, 1, 1, 49.00),
  (7, 6, 2, 29.00),
  (8, 5, 1, 899.00),
  (8, 2, 1, 199.00);
