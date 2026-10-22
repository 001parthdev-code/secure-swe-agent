//! E2 transaction lifecycle validation.
//!
//! This module tracks legal transitions; it does NOT provide OS isolation,
//! version verification, or an atomic filesystem commit by itself.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum State {
    Requested,
    Authorized,
    Resolved,
    Locked,
    VersionVerified,
    Staged,
    Synced,
    Revalidated,
    Committed,
    Finalized,
    Aborted,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransitionError {
    InvalidTransition,
    AlreadyCommitted,
}

#[derive(Debug)]
pub struct Transaction {
    state: State,
}

impl Transaction {
    pub fn new() -> Self {
        Self {
            state: State::Requested,
        }
    }

    pub fn state(&self) -> State {
        self.state
    }

    pub fn advance(&mut self, next: State) -> Result<(), TransitionError> {
        use State::*;
        let valid = matches!(
            (self.state, next),
            (Requested, Authorized)
                | (Authorized, Resolved)
                | (Resolved, Locked)
                | (Locked, VersionVerified)
                | (VersionVerified, Staged)
                | (Staged, Synced)
                | (Synced, Revalidated)
                | (Revalidated, Committed)
                | (Committed, Finalized)
        );
        if valid {
            self.state = next;
            Ok(())
        } else if self.state == Committed || self.state == Finalized {
            Err(TransitionError::AlreadyCommitted)
        } else {
            Err(TransitionError::InvalidTransition)
        }
    }

    pub fn abort(&mut self) -> Result<(), TransitionError> {
        if matches!(self.state, State::Committed | State::Finalized) {
            return Err(TransitionError::AlreadyCommitted);
        }
        self.state = State::Aborted;
        Ok(())
    }
}

impl Default for Transaction {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn valid_transaction_reaches_finalized() {
        let mut tx = Transaction::new();
        for next in [
            State::Authorized,
            State::Resolved,
            State::Locked,
            State::VersionVerified,
            State::Staged,
            State::Synced,
            State::Revalidated,
            State::Committed,
            State::Finalized,
        ] {
            tx.advance(next).unwrap();
        }
        assert_eq!(tx.state(), State::Finalized);
    }

    #[test]
    fn cannot_skip_security_preconditions() {
        let mut tx = Transaction::new();
        assert_eq!(
            tx.advance(State::Committed),
            Err(TransitionError::InvalidTransition)
        );
        assert_eq!(tx.state(), State::Requested);
    }

    #[test]
    fn abort_is_terminal_and_precommit_only() {
        let mut tx = Transaction::new();
        tx.advance(State::Authorized).unwrap();
        tx.abort().unwrap();
        assert_eq!(
            tx.advance(State::Resolved),
            Err(TransitionError::InvalidTransition)
        );
        let mut committed = Transaction::new();
        for next in [
            State::Authorized,
            State::Resolved,
            State::Locked,
            State::VersionVerified,
            State::Staged,
            State::Synced,
            State::Revalidated,
            State::Committed,
        ] {
            committed.advance(next).unwrap();
        }
        assert_eq!(committed.abort(), Err(TransitionError::AlreadyCommitted));
    }
}
