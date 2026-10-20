@editorial @contracts @classifier
Feature: Zero-shot classifier lane
  As an editor whose policies are judgment calls rather than word lists
  I want each sentence, paragraph and document classified against our guidelines by a decision model
  So that problems no regular expression can see are marked too, with how sure the model is

  Background:
    Given a fake decision model that answers "yes" with probability 0.95 for "trust us", 0.6 for "perhaps" and 0.05 otherwise
    And a policy pack with these classifier policies:
      | policy           | severity | scope     | question                                         | threshold | reviewAt |
      | concrete-claims  | warn     | sentence  | Does the target make a claim with no specifics?  | 0.8       | 0.5      |
      | no-unearned-trust| error    | sentence  | Does the target ask the reader to just trust it? | 0.8       |          |
      | focused          | info     | paragraph | Does the target paragraph wander off topic?      | 0.8       | 0.5      |

  Scenario: Sentences above the threshold are violations and the uncertain band needs review
    Given the document to classify is:
      """
      Our system is fast, trust us. It handles 40,000 requests a second.

      It is perhaps the best option.
      """
    When the document is classified
    Then the classifier lane reports status "ran" with 3 detectors
    And the findings are:
      | policy            | excerpt                        | status    | severity |
      | concrete-claims   | Our system is fast, trust us.  | violation | warn     |
      | no-unearned-trust | Our system is fast, trust us.  | violation | error    |
      | focused           | Our system is fast, trust us. It handles 40,000 requests a second. | violation | info |
      | concrete-claims   | It is perhaps the best option. | review    | warn     |
      | focused           | It is perhaps the best option. | review    | info     |
    And every classifier finding carries its probability
    And coverage has a probability for every sentence and paragraph against each of its detectors

  Scenario: One request per segment carries every question for that segment
    Given the document to classify is:
      """
      First sentence. Second sentence.
      """
    When the document is classified
    Then the decision model received 3 requests
    And each sentence request asked 2 questions and the paragraph request asked 1
    And each sentence request's state includes its paragraph as context

  Scenario: Rescanning after an edit only re-asks about changed text
    Given the document to classify is:
      """
      Unchanged paragraph here.

      This paragraph will change.
      """
    When the document is classified
    And the second paragraph becomes "This paragraph changed, trust us." and the document is classified again with the same cache
    Then the second check sent 2 requests to the decision model
    And the second check reports 2 cache hits

  Scenario: Choice and score questions map to a probability of violation
    Given the decision model answers a "choice" question with probabilities "neutral=0.2, hype=0.7, plain=0.1"
    And the decision model answers a "score" question with probabilities "0=0.5, 1=0.3, 2=0.2"
    When a choice detector with violation labels "hype, neutral" is evaluated
    And a score detector with violation "scoreBelow 2" is evaluated
    Then the choice detector's probability of violation is 0.9
    And the score detector's probability of violation is 0.8

  Scenario: Without a decision model the classifier lane is unavailable but rules still run
    Given no decision model is configured
    And the pack also has a phrase rule for "trust us"
    And the document to classify is:
      """
      Our system is fast, trust us.
      """
    When the document is classified
    Then the classifier lane reports status "unavailable"
    And the rules lane still reports its finding

  Scenario: A failing decision model does not fail the check
    Given a decision model that fails every request
    And the document to classify is:
      """
      Our system is fast, trust us.
      """
    When the document is classified
    Then the classifier lane reports status "failed"
    And the check result is a valid "check-result-v1" document

  Scenario: A token budget stops the lane early and says so
    Given the document to classify is:
      """
      One. Two. Three. Four. Five.
      """
    And the classifier budget is 1000 input tokens with each request costing 400
    When the document is classified
    Then the classifier lane reports status "partial"
    And the decision model received 2 requests
