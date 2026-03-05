-- =============================================================================
-- Finance Governance Demo – Seed Data
-- Target: trial.default
-- Creates 7 tables spanning all sensitivity labels:
--   pii, pci, confidential, time_sensitive, public
-- =============================================================================

USE CATALOG trial;
USE SCHEMA default;

-- ---------------------------------------------------------------------------
-- 1. customers – heavy PII (name, email, phone, SSN, DOB, address)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE customers (
  customer_id       BIGINT        GENERATED ALWAYS AS IDENTITY,
  first_name        STRING        COMMENT 'Customer first name',
  last_name         STRING        COMMENT 'Customer last name',
  email             STRING        COMMENT 'Primary email address',
  phone_number      STRING        COMMENT 'Mobile phone number',
  ssn               STRING        COMMENT 'Social Security Number',
  date_of_birth     DATE          COMMENT 'Date of birth',
  street_address    STRING,
  city              STRING,
  state             STRING,
  zip_code          STRING,
  created_at        TIMESTAMP
);

INSERT INTO customers (first_name, last_name, email, phone_number, ssn, date_of_birth, street_address, city, state, zip_code) VALUES
  ('Amara',  'Okonkwo',  'amara.okonkwo@example.com',   '415-555-0101', '123-45-6789', '1985-03-14', '742 Evergreen Ter',   'San Francisco', 'CA', '94110'),
  ('Raj',    'Mehta',    'raj.mehta@example.com',        '212-555-0142', '987-65-4321', '1990-07-22', '350 Fifth Ave',       'New York',      'NY', '10118'),
  ('Sofia',  'Alvarez',  'sofia.alvarez@example.com',    '312-555-0183', '456-78-9012', '1978-11-03', '233 S Wacker Dr',     'Chicago',       'IL', '60606'),
  ('Liam',   'Chen',     'liam.chen@example.com',        '206-555-0124', '321-54-9876', '1995-01-30', '400 Broad St',        'Seattle',       'WA', '98109'),
  ('Fatima', 'Al-Rashid','fatima.alrashid@example.com',  '617-555-0199', '654-32-1098', '1988-09-17', '1 Congress St',       'Boston',        'MA', '02114');

-- ---------------------------------------------------------------------------
-- 2. payment_methods – PCI (card numbers, CVV, expiry, cardholder name)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE payment_methods (
  payment_id        BIGINT        GENERATED ALWAYS AS IDENTITY,
  customer_id       BIGINT        NOT NULL,
  cardholder_name   STRING        COMMENT 'Name printed on card',
  card_number       STRING        COMMENT 'Full credit/debit card number',
  card_expiry       STRING        COMMENT 'Card expiration MM/YY',
  cvv               STRING        COMMENT 'Card verification value',
  billing_zip       STRING,
  card_type         STRING        COMMENT 'visa, mastercard, amex',
  is_default        BOOLEAN
);

INSERT INTO payment_methods (customer_id, cardholder_name, card_number, card_expiry, cvv, billing_zip, card_type, is_default) VALUES
  (1, 'Amara Okonkwo',    '4111-1111-1111-1111', '09/27', '314', '94110', 'visa',       true),
  (2, 'Raj Mehta',        '5500-0000-0000-0004', '12/26', '827', '10118', 'mastercard', true),
  (3, 'Sofia Alvarez',    '3400-0000-0000-009',  '03/28', '4921','60606', 'amex',       true),
  (4, 'Liam Chen',        '4222-2222-2222-2222', '06/27', '553', '98109', 'visa',       false),
  (4, 'Liam Chen',        '5100-0000-0000-0008', '11/26', '901', '98109', 'mastercard', true),
  (5, 'Fatima Al-Rashid', '4000-0000-0000-0002', '01/28', '672', '02114', 'visa',       true);

-- ---------------------------------------------------------------------------
-- 3. transactions – PCI + confidential (amounts, merchant, card refs)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE transactions (
  txn_id            BIGINT        GENERATED ALWAYS AS IDENTITY,
  customer_id       BIGINT        NOT NULL,
  payment_id        BIGINT        NOT NULL,
  txn_date          TIMESTAMP,
  amount            DECIMAL(12,2) COMMENT 'Transaction amount in USD',
  currency          STRING,
  merchant_name     STRING,
  merchant_category STRING        COMMENT 'MCC category',
  card_last_four    STRING        COMMENT 'Last 4 digits of card used',
  status            STRING        COMMENT 'approved, declined, pending'
);

INSERT INTO transactions (customer_id, payment_id, txn_date, amount, currency, merchant_name, merchant_category, card_last_four, status) VALUES
  (1, 1, '2025-12-01 09:14:00', 1249.99, 'USD', 'Cloud Corp SaaS',       'Software',      '1111', 'approved'),
  (1, 1, '2025-12-03 14:32:00',   89.50, 'USD', 'Office Depot',          'Office Supply',  '1111', 'approved'),
  (2, 2, '2025-12-05 11:05:00', 5400.00, 'USD', 'AWS Services',          'Cloud Infra',    '0004', 'approved'),
  (3, 3, '2025-12-07 16:48:00',  320.75, 'USD', 'Delta Airlines',        'Travel',         '0009', 'approved'),
  (4, 5, '2025-12-10 08:22:00', 15000.00,'USD', 'Databricks Inc',        'Software',       '0008', 'approved'),
  (4, 4, '2025-12-11 19:55:00',   42.00, 'USD', 'Uber Eats',             'Food Delivery',  '2222', 'declined'),
  (5, 6, '2025-12-15 10:30:00', 8750.00, 'USD', 'Snowflake Computing',   'Software',       '0002', 'approved'),
  (2, 2, '2025-12-18 13:12:00',  199.00, 'USD', 'GitHub Enterprise',     'Software',       '0004', 'approved');

-- ---------------------------------------------------------------------------
-- 4. employee_compensation – confidential (salary, bonus, equity)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE employee_compensation (
  employee_id       BIGINT        GENERATED ALWAYS AS IDENTITY,
  full_name         STRING        COMMENT 'Employee full legal name',
  employee_email    STRING        COMMENT 'Corporate email',
  department        STRING,
  job_title         STRING,
  base_salary       DECIMAL(12,2) COMMENT 'Annual base salary USD',
  bonus_target_pct  DECIMAL(5,2)  COMMENT 'Target bonus as percent of base',
  stock_grant_units INT           COMMENT 'RSU units granted',
  hire_date         DATE,
  manager_name      STRING
);

INSERT INTO employee_compensation (full_name, employee_email, department, job_title, base_salary, bonus_target_pct, stock_grant_units, hire_date, manager_name) VALUES
  ('Priya Kapoor',    'priya.kapoor@acmefin.com',    'Engineering',  'Staff Engineer',       195000.00, 20.00, 4500, '2019-03-15', 'David Park'),
  ('Marcus Johnson',  'marcus.johnson@acmefin.com',  'Engineering',  'Senior Engineer',      172000.00, 15.00, 3000, '2020-08-01', 'David Park'),
  ('Elena Voss',      'elena.voss@acmefin.com',      'Finance',      'VP of Finance',        245000.00, 30.00, 8000, '2018-01-10', 'Sarah Kim'),
  ('David Park',      'david.park@acmefin.com',      'Engineering',  'Director of Eng',      230000.00, 25.00, 7000, '2017-06-20', 'Sarah Kim'),
  ('Sarah Kim',       'sarah.kim@acmefin.com',       'Executive',    'CTO',                  320000.00, 40.00,15000, '2016-02-01', NULL),
  ('James O''Brien',  'james.obrien@acmefin.com',    'Data Science', 'ML Engineer',          165000.00, 15.00, 2500, '2021-11-12', 'David Park');

-- ---------------------------------------------------------------------------
-- 5. session_tokens – time_sensitive (tokens, OTPs, temp credentials)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE session_tokens (
  token_id          BIGINT        GENERATED ALWAYS AS IDENTITY,
  customer_id       BIGINT        NOT NULL,
  session_token     STRING        COMMENT 'Bearer session token',
  otp_code          STRING        COMMENT 'One-time password for MFA',
  refresh_token     STRING        COMMENT 'OAuth refresh token',
  ip_address        STRING        COMMENT 'Client IP address',
  user_agent        STRING,
  issued_at         TIMESTAMP,
  expires_at        TIMESTAMP     COMMENT 'Token expiry time',
  is_active         BOOLEAN
);

INSERT INTO session_tokens (customer_id, session_token, otp_code, refresh_token, ip_address, user_agent, issued_at, expires_at, is_active) VALUES
  (1, 'eyJhbGciOi.tok_amara_01',  '384291', 'ref_amara_01xx',  '203.0.113.42',  'Chrome/120', '2025-12-20 08:00:00', '2025-12-20 09:00:00', false),
  (1, 'eyJhbGciOi.tok_amara_02',  '710583', 'ref_amara_02xx',  '203.0.113.42',  'Chrome/120', '2025-12-20 14:00:00', '2025-12-20 15:00:00', true),
  (2, 'eyJhbGciOi.tok_raj_01',    '925104', 'ref_raj_01xxxx',  '198.51.100.17', 'Firefox/121','2025-12-19 11:30:00', '2025-12-19 12:30:00', false),
  (3, 'eyJhbGciOi.tok_sofia_01',  '463827', 'ref_sofia_01xx',  '192.0.2.88',    'Safari/17',  '2025-12-21 09:15:00', '2025-12-21 10:15:00', true),
  (5, 'eyJhbGciOi.tok_fatima_01', '158739', 'ref_fatima_01x',  '10.0.0.55',     'Edge/120',   '2025-12-21 16:45:00', '2025-12-21 17:45:00', true);

-- ---------------------------------------------------------------------------
-- 6. accounts – PII + confidential (account numbers, balances)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE accounts (
  account_id        BIGINT        GENERATED ALWAYS AS IDENTITY,
  customer_id       BIGINT        NOT NULL,
  account_number    STRING        COMMENT 'Bank account number',
  routing_number    STRING        COMMENT 'ABA routing number',
  account_type      STRING        COMMENT 'checking, savings, investment',
  balance           DECIMAL(14,2) COMMENT 'Current balance in USD',
  credit_limit      DECIMAL(14,2),
  opened_date       DATE,
  status            STRING
);

INSERT INTO accounts (customer_id, account_number, routing_number, account_type, balance, credit_limit, opened_date, status) VALUES
  (1, '****-****-7823', '021000021', 'checking',   14520.83,  NULL,      '2019-05-10', 'active'),
  (1, '****-****-9901', '021000021', 'savings',    87340.00,  NULL,      '2019-05-10', 'active'),
  (2, '****-****-3345', '026009593', 'checking',   52100.47,  NULL,      '2020-01-22', 'active'),
  (3, '****-****-6610', '071000013', 'investment', 245890.15,  NULL,      '2018-09-03', 'active'),
  (4, '****-****-2289', '125000024', 'checking',    8350.00,  25000.00,  '2021-03-17', 'active'),
  (5, '****-****-5574', '011401533', 'savings',   132000.00,  NULL,      '2017-11-28', 'active');

-- ---------------------------------------------------------------------------
-- 7. loan_applications – PII + PCI + confidential (credit score, income)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE loan_applications (
  application_id    BIGINT        GENERATED ALWAYS AS IDENTITY,
  customer_id       BIGINT        NOT NULL,
  applicant_name    STRING        COMMENT 'Full legal name on application',
  applicant_ssn     STRING        COMMENT 'SSN for credit check',
  annual_income     DECIMAL(12,2) COMMENT 'Self-reported annual income',
  credit_score      INT           COMMENT 'FICO credit score',
  loan_amount       DECIMAL(12,2),
  loan_purpose      STRING        COMMENT 'mortgage, auto, personal, business',
  interest_rate     DECIMAL(5,3),
  term_months       INT,
  decision          STRING        COMMENT 'approved, denied, under_review',
  applied_at        TIMESTAMP
);

INSERT INTO loan_applications (customer_id, applicant_name, applicant_ssn, annual_income, credit_score, loan_amount, loan_purpose, interest_rate, term_months, decision) VALUES
  (1, 'Amara Okonkwo',    '123-45-6789', 145000.00, 782, 450000.00, 'mortgage', 6.125, 360, 'approved'),
  (2, 'Raj Mehta',        '987-65-4321', 210000.00, 801, 35000.00,  'auto',     4.750,  60, 'approved'),
  (3, 'Sofia Alvarez',    '456-78-9012', 185000.00, 745, 75000.00,  'business', 7.500,  84, 'approved'),
  (4, 'Liam Chen',        '321-54-9876',  92000.00, 698, 25000.00,  'personal', 9.250,  48, 'under_review'),
  (5, 'Fatima Al-Rashid', '654-32-1098', 168000.00, 770, 520000.00, 'mortgage', 5.875, 360, 'approved');
