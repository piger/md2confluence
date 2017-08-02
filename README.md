# md2confluence

A script to import Markdown documents as Confluence wiki pages.

## Example usage

For each page to import you have to create a metadata file; for example to import the document `notes.md`
you need to create `notes.md.meta` having the contents:

```
id = confluence page id
space = confluence space
title = the title of your page
```

To configure authentication for jira you need to set three environment variables: `JIRA_USERNAME`,
`JIRA_PASSWORD`, `JIRA_DOMAIN`.

Now you can finally run:

``` shell
md2confluence notes.md
```

to import your page into Confluence. Please note that at the moment you can only update already existsing pages.

## Useful documentation

- https://confluence.atlassian.com/doc/code-block-macro-139390.html
- https://developer.atlassian.com/confdev/confluence-server-rest-api/confluence-rest-api-examples
- https://confluence.atlassian.com/doc/confluence-wiki-markup-251003035.html
