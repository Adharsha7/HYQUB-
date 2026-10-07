// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @notice Minimal contract used only in tests to prove HYQUBWallet.execute()
///         can drive an arbitrary contract call, not just plain ETH transfers.
contract TestTarget {
    uint256 public value;

    event ValueSet(uint256 newValue);

    function setValue(uint256 _value) external {
        value = _value;
        emit ValueSet(_value);
    }
}
