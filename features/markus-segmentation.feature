@editorial @contracts
Feature: Segment Markus documents into paragraphs and sentences
  As a lane that judges prose paragraph by paragraph and sentence by sentence
  I want every prose segment with exact source offsets and stable ids
  So that findings land on the right text and survive unrelated edits

  Scenario: Paragraphs and sentences carry exact source offsets
    Given the Markus document:
      """
      ---
      title: Example
      ---
      # A heading

      First sentence here. Second one, e.g. with an abbreviation, ends here! Third?

      - A list item that is prose.
      """
    When the document is segmented
    Then the paragraph segments are:
      | block    | source                                                                         |
      | heading  | A heading                                                                      |
      | paragraph | First sentence here. Second one, e.g. with an abbreviation, ends here! Third? |
      | listItem | A list item that is prose.                                                     |
    And the sentence segments of paragraph 2 are:
      | source                                              |
      | First sentence here.                                |
      | Second one, e.g. with an abbreviation, ends here!   |
      | Third?                                              |
    And every segment's offsets select its source from the document
    And the front matter is a protected "frontMatter" region

  Scenario: Structural markup is protected rather than treated as prose
    Given the Markus document:
      """
      Intro paragraph.

      ::image{
        src="images/chart.png"
        alt="A chart. It has two sentences."
      }

      ```python
      print("not prose. really.")
      ```

      > Someone else's words. Leave them alone.

      Closing paragraph.
      """
    When the document is segmented
    Then the paragraph segments are:
      | block     | source             |
      | paragraph | Intro paragraph.   |
      | paragraph | Closing paragraph. |
    And the protected regions are "directive, code, quote"
    And no segment overlaps a protected region

  Scenario: Table cells are prose and the table syntax is not
    Given the Markus document:
      """
      Before the table.

      | Metric | Claim |
      |:-------|------:|
      | Speed  | Runs **fast**. It never fails. |
      | Count  | 1,200 |
      | Call   | `run()` |
      | Pipe   | in-cell text |

      After the table.
      """
    When the document is segmented
    Then the paragraph segments are:
      | block     | source                          |
      | paragraph | Before the table.               |
      | tableCell | Metric                          |
      | tableCell | Claim                           |
      | tableCell | Speed                           |
      | tableCell | Runs **fast**. It never fails.  |
      | tableCell | Count                           |
      | tableCell | Call                            |
      | tableCell | Pipe                            |
      | tableCell | in-cell text                    |
      | paragraph | After the table.                |
    And the sentence segments of paragraph 5 are:
      | source               |
      | Runs **fast**.       |
      | It never fails.      |
    And every segment's offsets select its source from the document
    And the document has no protected regions

  Scenario: Container directive content is prose
    Given the Markus document:
      """
      :::callout{kind="note"}
      Inside the callout. Still prose.
      :::
      """
    When the document is segmented
    Then the paragraph segments are:
      | block     | source                           |
      | paragraph | Inside the callout. Still prose. |
    And the protected regions are "directive, directive"

  Scenario: Sentences do not split inside links, code, citations, numbers or abbreviations
    Given the Markus document:
      """
      See [the docs](https://example.com/a.b?c=1). Version 2.5 added `x.y()` for Dr. Smith [@smith2020]. Done.
      """
    When the document is segmented
    Then the sentence segments of paragraph 1 are:
      | source                                                   |
      | See [the docs](https://example.com/a.b?c=1).             |
      | Version 2.5 added `x.y()` for Dr. Smith [@smith2020].    |
      | Done.                                                    |
    And the plain text of sentence 1 is "See the docs."

  Scenario: Repeated paragraphs are separate segments at their own offsets
    Given the Markus document:
      """
      Same words.

      Different words.

      Same words.
      """
    When the document is segmented
    Then there are 3 paragraph segments
    And paragraph 1 and paragraph 3 have different ids and different offsets
    And every segment's offsets select its source from the document

  Scenario: Segment ids survive edits to other paragraphs
    Given the Markus document:
      """
      Stable paragraph. It does not change.

      Edited paragraph.
      """
    When the document is segmented
    And the second paragraph is rewritten and the document is segmented again
    Then the first paragraph and its sentences keep their ids
