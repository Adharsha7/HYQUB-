// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title HYQUBWallet - Stage 1: Foundation
/// @notice Owner, constructor, nonce, events, and access control
contract HYQUBWallet {
    // ------------------------------------------------------------------
    // State Variables
    // ------------------------------------------------------------------

    /// @notice The address that controls this wallet
    address public owner;

    /// @notice Incremented on every executed transaction to prevent replay attacks
    uint256 public nonce;

    // ------------------------------------------------------------------
    // Events
    // ------------------------------------------------------------------

    event WalletCreated(address indexed owner);
    event NonceIncremented(uint256 newNonce);
    event Deposited(address indexed from, uint256 amount);
    event Withdrawn(address indexed to, uint256 amount);
    event Executed(address indexed target, uint256 value, bytes data, bytes result);

    // ------------------------------------------------------------------
    // Access Control
    // ------------------------------------------------------------------

    modifier onlyOwner() {
        require(msg.sender == owner, "HYQUBWallet: caller is not the owner");
        _;
    }

    // ------------------------------------------------------------------
    // Constructor
    // ------------------------------------------------------------------

    constructor() {
        owner = msg.sender;
        emit WalletCreated(owner);
    }

    // ------------------------------------------------------------------
    // Internal Helpers
    // ------------------------------------------------------------------

    function _incrementNonce() internal {
        nonce++;
        emit NonceIncremented(nonce);
    }

    // ------------------------------------------------------------------
    // Stage 2: ETH Deposit, Withdrawal, and Transaction Execution
    // ------------------------------------------------------------------

    receive() external payable {
        emit Deposited(msg.sender, msg.value);
    }

    function deposit() external payable {
        require(msg.value > 0, "HYQUBWallet: deposit must be > 0");
        emit Deposited(msg.sender, msg.value);
    }

    function withdraw(address payable to, uint256 amount) external onlyOwner {
        require(to != address(0), "HYQUBWallet: cannot withdraw to zero address");
        require(amount > 0, "HYQUBWallet: amount must be > 0");
        require(address(this).balance >= amount, "HYQUBWallet: insufficient balance");

        _incrementNonce();

        (bool success, ) = to.call{value: amount}("");
        require(success, "HYQUBWallet: withdrawal transfer failed");

        emit Withdrawn(to, amount);
    }

    function execute(address target, uint256 value, bytes calldata data)
        external
        onlyOwner
        returns (bytes memory result)
    {
        require(target != address(0), "HYQUBWallet: target cannot be zero address");
        require(address(this).balance >= value, "HYQUBWallet: insufficient balance for call");

        _incrementNonce();

        bool success;
        (success, result) = target.call{value: value}(data);
        require(success, "HYQUBWallet: execution failed");

        emit Executed(target, value, data, result);
    }

    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }
}
