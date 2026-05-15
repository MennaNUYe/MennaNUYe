-- Optional MySQL triggers for event-driven product marketing workflows.
-- Replace wp_ if your WP_TABLE_PREFIX differs. Run with a privileged DBA account.

CREATE TABLE IF NOT EXISTS wp_product_automation_events (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  product_id BIGINT UNSIGNED NOT NULL,
  event_type VARCHAR(32) NOT NULL,
  meta_key VARCHAR(64) NULL,
  old_value LONGTEXT NULL,
  new_value LONGTEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processed_at TIMESTAMP NULL,
  INDEX idx_processed_created (processed_at, created_at),
  INDEX idx_product (product_id)
);

DELIMITER $$

CREATE TRIGGER wp_product_price_stock_insert_event
AFTER INSERT ON wp_postmeta
FOR EACH ROW
BEGIN
  IF NEW.meta_key IN ('_price', '_regular_price', '_stock') THEN
    INSERT INTO wp_product_automation_events(product_id, event_type, meta_key, new_value)
    VALUES (NEW.post_id, 'meta_insert', NEW.meta_key, NEW.meta_value);
  END IF;
END$$

CREATE TRIGGER wp_product_price_stock_update_event
AFTER UPDATE ON wp_postmeta
FOR EACH ROW
BEGIN
  IF NEW.meta_key IN ('_price', '_regular_price', '_stock') AND COALESCE(OLD.meta_value, '') <> COALESCE(NEW.meta_value, '') THEN
    INSERT INTO wp_product_automation_events(product_id, event_type, meta_key, old_value, new_value)
    VALUES (NEW.post_id, 'meta_update', NEW.meta_key, OLD.meta_value, NEW.meta_value);
  END IF;
END$$

CREATE TRIGGER wp_product_publish_event
AFTER INSERT ON wp_posts
FOR EACH ROW
BEGIN
  IF NEW.post_type = 'product' AND NEW.post_status = 'publish' THEN
    INSERT INTO wp_product_automation_events(product_id, event_type)
    VALUES (NEW.ID, 'product_publish');
  END IF;
END$$

DELIMITER ;
