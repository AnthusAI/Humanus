@editorial @contracts @calibration
Feature: Learn from editor decisions
  As a publication whose editors accept, fix or dismiss classifier findings
  I want those decisions to correct the model's confidence and teach it by example
  So that "violation" means what our editors mean, and dismissals stop recurring

  Scenario: Calibration reduces calibration error on held-out decisions
    Given 3000 editor decisions on an overconfident detector
    When I calibrate the detector on the first 2000 decisions
    Then the calibration method is "isotonic"
    And the calibration is valid inside a policy pack
    And the expected calibration error on the last 1000 decisions drops by at least half

  Scenario Outline: The calibration method depends on how many decisions there are
    Given <count> editor decisions on an overconfident detector
    When I calibrate the detector on all of them
    Then the calibration result is "<result>"

    Examples:
      | count | result            |
      | 5     | not enough labels |
      | 20    | platt             |
      | 120   | isotonic          |

  Scenario: Thresholds apply to the calibrated probability
    Given a sentence detector with threshold 0.8 and review from 0.5 whose model says 0.95
    And its calibration maps 0.95 down to 0.6
    When the sentence is checked
    Then the finding has status "review" with probability 0.6 and raw probability 0.95

  Scenario: Past decisions most like the target travel with the question as examples
    Given past decisions for detector "vague" with texts:
      | text                                              | violates |
      | Our platform is incredibly fast.                  | yes      |
      | Our platform answers in 40 milliseconds.          | no       |
      | The weather in Paris was mild last spring.        | no       |
      | Our service is extremely reliable.                | yes      |
    And at most 2 examples per question
    When the sentence "Our platform is extremely fast." is checked with those examples
    Then the question for detector "vague" carried 2 examples
    And the examples were "Our platform is incredibly fast." and "Our service is extremely reliable."
