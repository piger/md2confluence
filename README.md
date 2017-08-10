# md2confluence

A script to import Markdown documents as Confluence wiki pages.

## Confluence syntax

The amount of Confluence "Storage" syntax (**not markup!**)  supported is very limited and includes:

- code blocks
- image attachments
- popups (i.e. popup-like blocks for warning, note or info messages)

## Example usage

Each Markdown document that you want to import must have a *meta* header in the following format:

```
id: confluence page id
space: confluence space
title: the title of your page
```

This configure where the page will be uploaded to Confluence: the page ID of the page to overwrite, (for example the page at https://example.atlassian.net/wiki/pages/viewinfo.action?pageId=263915044 has the id `263915044`), the
Confluence *Space* (for example: "ops") and the title.

To configure authentication for jira you need to set three environment variables: `JIRA_USERNAME`,
`JIRA_PASSWORD`, `JIRA_DOMAIN`.

Now you can finally run:

``` shell
md2confluence notes.md
```

to import your page into Confluence. Please note that at the moment you can only update already existsing pages.

### Adding image attachments

In your markdown document you can use the standard syntax for image links:

``` markdown
![project_logo](project_logo.png)
```

if `project_logo.png` exists in the current directory it will be uploaded alongside the page being updated.

## Useful documentation

- https://confluence.atlassian.com/doc/code-block-macro-139390.html
- https://developer.atlassian.com/confdev/confluence-server-rest-api/confluence-rest-api-examples
- https://confluence.atlassian.com/doc/confluence-wiki-markup-251003035.html
- [Confluence storage format](https://confluence.atlassian.com/doc/confluence-storage-format-790796544.html)
