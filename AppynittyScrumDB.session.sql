-- created_on default
IF NOT EXISTS (
  SELECT 1 FROM sys.default_constraints
  WHERE parent_object_id = OBJECT_ID('dbo.projects')
    AND name = 'DF_projects_created_on'
)
BEGIN
  ALTER TABLE dbo.projects
    ADD CONSTRAINT DF_projects_created_on
    DEFAULT (SYSUTCDATETIME()) FOR created_on;
END

-- last_modified default
IF NOT EXISTS (
  SELECT 1 FROM sys.default_constraints
  WHERE parent_object_id = OBJECT_ID('dbo.projects')
    AND name = 'DF_projects_last_modified'
)
BEGIN
  ALTER TABLE dbo.projects
    ADD CONSTRAINT DF_projects_last_modified
    DEFAULT (SYSUTCDATETIME()) FOR last_modified;
END
