-- SQLite seed for workshop1 (api/app/models.py).
-- Adapted from the PostgreSQL export district2_restaurants_reviews.postgres.sql.
--
-- The original script does not match this database:
--   * PostgreSQL public schema and UUID primary keys
--   * ON CONFLICT (id) — this app uses integer autoincrement ids
--   * NULL google_place_id — restaurants.google_place_id is NOT NULL and UNIQUE
--   * NULL review rating / published_at — both columns are NOT NULL
--
-- This script upserts restaurants on google_place_id and reviews on external_review_id.
-- Unresolved Place IDs are stored as pending:<source-uuid>.
-- Missing review stars use the restaurant Google rating. Missing publish times use
-- the snapshot instant 2026-11-14T12:18:00+07:00 stored as UTC 2026-11-14 05:18:00.
-- Safe to re-run. Requires tables already created (python load_district2.py does that).
BEGIN;

INSERT INTO restaurants (google_place_id, name, address, google_rating, user_rating_count, last_synced_at, updated_at) VALUES
  ('ChIJ5bQZp8QndTERPZLM-v3IX58', 'Kichi Kichi Vincom Thảo Điền', 'L5-15+16, tầng 5, Vincom Mega Mall, 161 Võ Nguyên Giáp, An Khánh, Ho Chi Minh City, Vietnam', 4.5, 438, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJaddvvaovdTERNMfvQvz-07w', 'iSushi Thiso Mall Mai Chí Thọ', '53 Đ. Hoàng Thế Thiện, An Khánh, Ho Chi Minh City, Vietnam', 4.7, 928, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJDQyaHpIndTERwpku_POfi00', 'Meat & Meet BBQ - Estella', '01 Song Hành, Bình Trưng, Ho Chi Minh City, Vietnam', 4.4, 1565, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJSzWHFHAndTERMmYJlHWOlTk', 'AMERICANO COFFEE - 409 Nguyễn Duy Trinh', '409 Nguyễn Duy Trinh, Bình Trưng, Ho Chi Minh City, Vietnam', 4.6, 1303, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJQYz0dJwndTERpahorGuG85o', 'The Pizza Company Song Hành', '81 Song Hành, khu đô thị An Phú An Khánh, Bình Trưng, Ho Chi Minh City, Vietnam', 4.1, 560, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJgThOEPYndTERysyVVb-LNo4', 'con gà mái', 'QPXM+PJ4, 6 Song Hành, Khu đô thị An Phú An Khánh, An Khánh, Ho Chi Minh City, Vietnam', 3.9, 536, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJqcLuCZUndTERlVdqcH23880', 'Kitchen by the River', '02-04 Đường số 10, An Khánh, Ho Chi Minh City, Vietnam', 4.1, 141, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJHcH6sacndTERN23Gjx5SPfA', '들깨시래기 Perilla Korean restaurant', '2 Võ Trường Toản, An Khánh, Ho Chi Minh City, Vietnam', 4.1, 404, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJ8Qkl4hMmdTERySOOQQ0edYo', 'The Pizza Company Vincom Thảo Điền', 'TTTM Vincom, 159 Võ Nguyên Giáp, An Khánh, Ho Chi Minh City, Vietnam', 4.1, 333, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJFQtAYLcndTERK_AjlC7x2BI', 'I HATE MONDAY DINING', '25A Nguyễn Duy Hiệu, An Khánh, Ho Chi Minh City, Vietnam', 4.2, 865, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJC-JX7wgndTERaW-9HKtBU8Y', 'BBQ Plan-K Masteri', '175 Võ Nguyên Giáp, An Khánh, Ho Chi Minh City, Vietnam', 4.3, 638, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJ4330MZqzoDERUqzJOaamhL4', 'Basta Hiro - Pasta & Pizza (Estella Place)', '88 Song Hành, Estella Place, Bình Trưng, Ho Chi Minh City, Vietnam', 4.3, 479, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJ6SpjLj8ndTERmITpTSMF9BM', 'BBQ Ông Mập Thảo Điền', '38 Trần Ngọc Diện, An Khánh, Ho Chi Minh City, Vietnam', 4.8, 1043, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJ12KKSOUndTEROGby3stVXZM', 'LONG WANG Tầng Trệt Cantavil An Phú', 'Cantavil An Phú, Song Hành Xa Lộ Hà Nội, Bình Trưng, Ho Chi Minh City, Vietnam', 4.9, 903, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('ChIJfamNDAgndTERJlkZTouxu5o', 'Haidilao Huoguo Estella Place', 'Tầng 3, Estella Place, 88 Song Hành, Bình Trưng, Ho Chi Minh City, Vietnam', 4.9, 10027, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('pending:78b89d73-d3c2-5b83-889b-b4cd3ba928f5', 'Capone’s Chicago Pizza and Beer', '8/3 Đường số 49B, An Khánh, Ho Chi Minh City, Vietnam', 4.3, 173, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('pending:d6f8cdbf-6245-5e02-bf5d-0ead9c9156fd', 'Ciao Bella', '39 Võ Trường Toản, An Khánh, Ho Chi Minh City, Vietnam', 4.4, 309, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('pending:d13d0b8e-c01c-5c79-b8a3-aa886d62a576', 'River View Restaurant and Coffee', '8/11 Đường số 49B, An Khánh, Ho Chi Minh City, Vietnam', 4.4, 487, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('pending:03aa404a-6f72-5a4f-9d78-d5bb8242cf02', 'Buongiorno', '23 Lê Văn Miến, An Khánh, Ho Chi Minh City, Vietnam', 4.3, 316, '2026-11-14 05:18:00', '2026-11-14 05:18:00'),
  ('pending:415272f6-bc0a-5557-b4cd-927b95b7ab22', 'Pendolasco', '30 Tống Hữu Định, An Khánh, Ho Chi Minh City, Vietnam', 4.5, 1801, '2026-11-14 05:18:00', '2026-11-14 05:18:00')
ON CONFLICT(google_place_id) DO UPDATE SET
  name = excluded.name,
  address = excluded.address,
  google_rating = excluded.google_rating,
  user_rating_count = excluded.user_rating_count,
  last_synced_at = excluded.last_synced_at,
  updated_at = excluded.updated_at;

-- Reviews. restaurant_id is resolved from google_place_id so integer keys stay stable.
INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, '1a54b78f-c4ba-502a-a85a-4b24eebb506b', 'J. H. L.', NULL, 3.9, 'The chicken salad and shredded chicken rice were the highlights, with tender chicken and generous portions. The lemongrass-braised chicken, however, was disappointing: the serving contained considerably more skin and bone than meat... Service could benefit from better training and greater attentiveness.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJgThOEPYndTERysyVVb-LNo4'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, '9150d30a-c3d8-5281-9603-475e71e6938f', 'V. A. N. N.', NULL, 3.9, 'Cơm gà Phú Yên is famous for its crispy scorched rice, flavorful chicken dishes, and delicious young chicken eggs. The chicken is tender and richly seasoned.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJgThOEPYndTERysyVVb-LNo4'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, '4345a6d8-5875-535e-be3e-a5b0d550ef94', 'M. A. V.', NULL, 3.9, 'Food is just meh, too oily and the chicken meat is not at all fresh. The rice looks sad, too dry and even not fully cooked... Staff looks burnt out and not friendly. I probably will never come back.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJgThOEPYndTERysyVVb-LNo4'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, 'd340c36f-e665-531b-97fb-f822431a002c', 'C. T.', NULL, 3.9, 'The menu here mainly features chicken dishes... the other dishes are decent, especially considering the price point... the staff is always enthusiastic about seating guests... most branches lack air conditioning.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJgThOEPYndTERysyVVb-LNo4'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, '55507627-7075-5ef7-ae72-b82e406fbeab', 'A. N.', NULL, 3.9, 'The food itself was flavorful — especially the chicken — but the portions felt a little small for the price... service was slower than expected... the space is comfortable enough, but it could use a bit more attention to cleanliness during peak hours.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJgThOEPYndTERysyVVb-LNo4'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, 'b2012c87-ce18-5c0e-891b-445a21c9df13', 'Manuel Aniceto Dias', NULL, 4.1, 'The main dishes are always the same but well-prepared... the secret lies in the side dishes or appetizers... they are divine and constantly changing and original...', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJHcH6sacndTERN23Gjx5SPfA'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, 'c5dedd29-3495-526a-adba-cec059455b79', 'Tran Hang', NULL, 4.1, 'We had a yummy dinner after yoga. The small side dishes "banchan" are plentiful... Real taste of Korean basic meal which price is very reasonable...', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJHcH6sacndTERN23Gjx5SPfA'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, 'bda3c67f-57af-5f37-95a9-072d39b324b4', 'ivan Kim', NULL, 4.1, 'Here is famous place for basic korean foods. All dish is delicious, and the staff is kind. Only one problem is.. sometimes, attitude of owner is not that good.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJHcH6sacndTERN23Gjx5SPfA'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, '063847b7-3103-5e41-941a-059532e7753b', 'Nhi Nguyen', NULL, 4.1, 'Personally the octopus was a bit plan for me but the fish and soup were pretty good. Will go back to taste crab. The menu is a little bit limited though.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJHcH6sacndTERN23Gjx5SPfA'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, '5b408150-4aa0-5cdc-b718-67899d55449a', 'Lola Jasmine', NULL, 4.1, 'The side dishes were sweet. The fish was thin, small, and lacked meat. I wish they would pay more attention to the taste.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJHcH6sacndTERN23Gjx5SPfA'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, '7e0d3794-566b-528c-8f0f-cce91da229e7', 'Nenna Lusiana', NULL, 4.2, 'The meals so fantastic, the ambiance wonderful, the drinks so pretty and refreshing... we can see edible flowers is in the ice ball...', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJFQtAYLcndTERK_AjlC7x2BI'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, 'a7c894a5-bf75-5212-ad2f-3867a4083cb9', 'Gordon Rademacher', NULL, 4.2, 'Generally a nice and cute place. Nice ambience... Menu is quite interesting and portions are pretty decent too.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJFQtAYLcndTERK_AjlC7x2BI'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, 'c7071e5c-5867-5502-9195-30fc8b621011', 'Tuyet Xuan Huynh', NULL, 4.2, 'The food is delicious, though a bit pricey. The presentation is beautiful, and I especially liked the truffle mushroom fries. The drinks are good as well.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJFQtAYLcndTERK_AjlC7x2BI'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, 'cae6626c-13db-5c36-9705-32daa006c6f8', 'Thùy Linh Trần Vũ', NULL, 4.2, 'The decoration is very modern and fun. I enjoy the atmosphere here a lot... The portion of food is hugeeee and quite tasty... The server - Bin is very considerate...', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJFQtAYLcndTERK_AjlC7x2BI'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, 'bf0a849e-f942-544d-995a-0cb4673aab0d', 'Zi', NULL, 4.2, 'The ambience at this place was PERFECTION — the perfect lighting, music volume and decor... The food was AMAZING and the staff were all incredibly friendly...', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJFQtAYLcndTERK_AjlC7x2BI'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, 'b29efb33-375d-50f6-a098-683459d7688a', 'Patrick', NULL, 5.0, 'Chi nhánh Thảo Điền - Thịt tươi ngon Vị kim chi không chua Vị món ăn kèm với mình hơi ngọt - Nhân viên nhiệt tình rất dễ thương... Các bạn nhân viên nướng luôn cho khách. Bàn ngoài trời khiến mình rất hài lòng. To, ngồi thoải mái, không khói. -Có chỗ để xe thoải mái.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJ6SpjLj8ndTERmITpTSMF9BM'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

INSERT INTO reviews (restaurant_id, external_review_id, author_name, author_uri, rating, text, published_at)
SELECT r.id, '0303d429-9868-55e4-93ba-7d259fabe212', 'Tom solomon', NULL, 3.0, 'Đồ ăn - Ngọt. Không đặc sắc - thịt bò mềm. Ổn - món ăn kèm không ngon... chỗ ngồi thoải mái - có chỗ để xe - vỉ nướng tốt. Nhân viên rất tốt... ít thức ăn so với giá tiền... Đồ ăn không đặc sắc để quay lại.', '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id = 'ChIJ6SpjLj8ndTERmITpTSMF9BM'
ON CONFLICT(external_review_id) DO UPDATE SET
  restaurant_id = excluded.restaurant_id,
  author_name = excluded.author_name,
  author_uri = excluded.author_uri,
  rating = excluded.rating,
  text = excluded.text,
  published_at = excluded.published_at;

-- Sync targets for resolved Google Place IDs only.
INSERT INTO sync_targets (target_type, value, language_code, is_active, last_synced_at)
SELECT 'place_id', r.google_place_id, 'vi', 1, '2026-11-14 05:18:00'
FROM restaurants r
WHERE r.google_place_id NOT LIKE 'pending:%'
  AND NOT EXISTS (
    SELECT 1 FROM sync_targets st
    WHERE st.target_type = 'place_id' AND st.value = r.google_place_id
  );

COMMIT;
