// SPDX-License-Identifier: MIT

pragma solidity ^0.8.19;

import "./HYQUBRegistry.sol";
import {IAccount} from "account-abstraction/interfaces/IAccount.sol";
import {PackedUserOperation} from "account-abstraction/interfaces/PackedUserOperation.sol";
import {IEntryPoint} from "account-abstraction/interfaces/IEntryPoint.sol";

/// @title HYQUBWallet
/// @notice HYQUB wallet foundation with Registry integration
///         and trusted approval-signer configuration.
contract HYQUBWallet is IAccount {

    // ------------------------------------------------------------------
    // State Variables
    // ------------------------------------------------------------------

    /// @notice The address that controls this wallet.
    address public owner;

    /// @notice HYQUB security registry associated with this wallet.
    HYQUBRegistry public immutable registry;

    /// @notice Trusted Ethereum address that signs HYQUB approval tokens.
    address public immutable approvalSigner;

    /// @notice The ERC-4337 EntryPoint authorized to call validateUserOp.
    address public immutable entryPoint;

    /// @notice Incremented on every executed transaction.
    uint256 public nonce;

    /// @notice Tracks which HYQUB approval nonces have already been
    ///         consumed by a successful validateUserOp, to prevent
    ///         a single backend approval being replayed.
    mapping(uint256 => bool) public usedApprovalNonces;

    // ------------------------------------------------------------------
    // Events
    // ------------------------------------------------------------------

    event WalletCreated(address indexed owner);

    event NonceIncremented(uint256 newNonce);

    event Deposited(address indexed from, uint256 amount);

    event Withdrawn(address indexed to, uint256 amount);

    event Executed(
        address indexed target,
        uint256 value,
        bytes data,
        bytes result
    );

    // ------------------------------------------------------------------
    // Access Control
    // ------------------------------------------------------------------

    modifier onlyOwner() {
        require(
            msg.sender == owner,
            "HYQUBWallet: caller is not the owner"
        );
        _;
    }

    /// @notice Allows either the wallet owner directly, or the configured
    ///         EntryPoint (after validateUserOp has already authorized the
    ///         call via the HYQUB approval check), to invoke execute().
    modifier onlyOwnerOrEntryPoint() {
        require(
            msg.sender == owner || msg.sender == entryPoint,
            "HYQUBWallet: caller is not the owner or EntryPoint"
        );
        _;
    }

    // ------------------------------------------------------------------
    // Constructor
    // ------------------------------------------------------------------

    constructor(
        address _registry,
        address _approvalSigner,
        address _entryPoint
    ) {
        require(
            _registry != address(0),
            "HYQUBWallet: registry cannot be zero"
        );

        require(
            _approvalSigner != address(0),
            "HYQUBWallet: approval signer cannot be zero"
        );

        require(
            _entryPoint != address(0),
            "HYQUBWallet: entryPoint cannot be zero"
        );

        owner = msg.sender;
        registry = HYQUBRegistry(_registry);
        approvalSigner = _approvalSigner;
        entryPoint = _entryPoint;

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
    // ETH Deposit
    // ------------------------------------------------------------------

    receive() external payable {
        emit Deposited(msg.sender, msg.value);
    }

    function deposit() external payable {
        require(
            msg.value > 0,
            "HYQUBWallet: deposit must be > 0"
        );

        emit Deposited(msg.sender, msg.value);
    }

    // ------------------------------------------------------------------
    // Withdrawal
    // ------------------------------------------------------------------

    function withdraw(
        address payable to,
        uint256 amount
    ) external onlyOwner {

        require(
            to != address(0),
            "HYQUBWallet: cannot withdraw to zero address"
        );

        require(
            amount > 0,
            "HYQUBWallet: amount must be > 0"
        );

        require(
            address(this).balance >= amount,
            "HYQUBWallet: insufficient balance"
        );

        _incrementNonce();

        (bool success, ) = to.call{value: amount}("");

        require(
            success,
            "HYQUBWallet: withdrawal transfer failed"
        );

        emit Withdrawn(to, amount);
    }

    // ------------------------------------------------------------------
    // Owner Transaction Execution
    // ------------------------------------------------------------------

    function execute(
        address target,
        uint256 value,
        bytes calldata data
    )
        external
        onlyOwnerOrEntryPoint
        returns (bytes memory result)
    {
        require(
            target != address(0),
            "HYQUBWallet: target cannot be zero address"
        );

        require(
            address(this).balance >= value,
            "HYQUBWallet: insufficient balance for call"
        );

        _incrementNonce();

        bool success;

        (success, result) = target.call{value: value}(data);

        require(
            success,
            "HYQUBWallet: execution failed"
        );

        emit Executed(
            target,
            value,
            data,
            result
        );
    }

    // ------------------------------------------------------------------
    // ERC-4337 Account Interface
    // ------------------------------------------------------------------

    uint256 internal constant SIG_VALIDATION_FAILED = 1;

    modifier onlyEntryPoint() {
        require(
            msg.sender == entryPoint,
            "HYQUBWallet: caller is not the EntryPoint"
        );
        _;
    }

    uint256 internal constant SIG_VALIDATION_SUCCESS = 0;

    function validateUserOp(
        PackedUserOperation calldata userOp,
        bytes32 userOpHash,
        uint256 missingAccountFunds
    )
        external
        onlyEntryPoint
        returns (uint256 validationData)
    {
        userOpHash; // not used directly; approval binds to TransactionIntent instead

        validationData = _validateHyqubApproval(userOp)
            ? SIG_VALIDATION_SUCCESS
            : SIG_VALIDATION_FAILED;

        _payPrefund(missingAccountFunds);
    }

    /// @dev Decodes userOp.signature as (approvalPayload, approvalSignature),
    ///      verifies the approval payload's structure, binds it to the
    ///      TransactionIntent implied by userOp.callData, recovers the
    ///      backend signer, and enforces single-use of the approval nonce.
    ///      Returns true only if every check passes.
    function _validateHyqubApproval(
        PackedUserOperation calldata userOp
    ) internal returns (bool) {
        (bytes memory approvalPayload, bytes memory approvalSignature) = abi
            .decode(userOp.signature, (bytes, bytes));

        (
            string memory tag,
            address approvedWallet,
            bytes32 messageHash,
            uint256 keyVersion,
            uint256 approvalNonce,
            uint256 issuedAt,
            string[] memory verifierIds
        ) = abi.decode(
            approvalPayload,
            (string, address, bytes32, uint256, uint256, uint256, string[])
        );

        issuedAt; // reserved for future expiry-window checks
        verifierIds; // reserved for future N-of-M quorum checks

        if (keccak256(bytes(tag)) != keccak256(bytes("HYQUB_APPROVAL_V1"))) {
            return false;
        }

        if (approvedWallet != address(this)) {
            return false;
        }

        if (usedApprovalNonces[approvalNonce]) {
            return false;
        }

        uint256 currentKeyVersion = registry.getKeyVersion(address(this));
        if (keyVersion != currentKeyVersion) {
            return false;
        }

        bytes32 expectedMessageHash = _reconstructTransactionIntentHash(
            userOp.callData
        );
        if (messageHash != expectedMessageHash) {
            return false;
        }

        bytes32 approvalHash = sha256(approvalPayload);
        address recovered = _recoverApprovalSigner(
            approvalHash,
            approvalSignature
        );
        if (recovered != approvalSigner) {
            return false;
        }

        usedApprovalNonces[approvalNonce] = true;
        return true;
    }

    /// @dev Same recovery scheme proven in ApprovalSignature.t.sol:
    ///      Ethereum Signed Message wrapper + ecrecover.
    function _recoverApprovalSigner(
        bytes32 payloadHash,
        bytes memory signature
    ) internal pure returns (address) {
        if (signature.length != 65) {
            return address(0);
        }

        bytes32 r;
        bytes32 s;
        uint8 v;

        assembly {
            r := mload(add(signature, 32))
            s := mload(add(signature, 64))
            v := byte(0, mload(add(signature, 96)))
        }

        if (v < 27) {
            v += 27;
        }

        bytes32 ethSignedMessageHash = keccak256(
            abi.encodePacked(
                "\x19Ethereum Signed Message:\n32",
                payloadHash
            )
        );

        return ecrecover(ethSignedMessageHash, v, r, s);
    }

    /// @notice Forwards any gas the EntryPoint says it's owed for this
    ///         validation/execution cycle. Called unconditionally from
    ///         validateUserOp, matching the reference SimpleAccount pattern.
    function _payPrefund(uint256 missingAccountFunds) internal {
        if (missingAccountFunds != 0) {
            (bool success, ) = payable(msg.sender).call{
                value: missingAccountFunds,
                gas: type(uint256).max
            }("");
            // Intentionally not reverting on failure: the EntryPoint checks
            // its own received balance and will revert the UserOperation
            // itself if the prefund is insufficient.
            (success);
        }
    }

    /// @notice Adds ETH to this wallet's deposit balance held at the EntryPoint.
    function addDeposit() external payable {
        IEntryPoint(entryPoint).depositTo{value: msg.value}(address(this));
    }

    /// @notice Returns this wallet's current deposit balance at the EntryPoint.
    function getDeposit() external view returns (uint256) {
        return IEntryPoint(entryPoint).balanceOf(address(this));
    }

    /// @notice Withdraws from this wallet's EntryPoint deposit to a chosen address.
    function withdrawDepositTo(
        address payable withdrawAddress,
        uint256 amount
    ) external onlyOwner {
        IEntryPoint(entryPoint).withdrawTo(withdrawAddress, amount);
    }

    // ------------------------------------------------------------------
    // TransactionIntent Reconstruction (Step 3)
    // ------------------------------------------------------------------

    /// @dev Matches the "HYQUB_TX_V1" canonical payload the backend signs:
    ///      abi.encode(chainId, wallet, target, value, data, keyVersion) → sha256
    error UnexpectedCallDataSelector(bytes4 selector);

    function _reconstructTransactionIntentHash(
        bytes calldata callData
    ) internal view returns (bytes32) {
        require(
            callData.length >= 4,
            "HYQUBWallet: callData too short"
        );

        bytes4 selector = bytes4(callData[:4]);

        if (selector != this.execute.selector) {
            revert UnexpectedCallDataSelector(selector);
        }

        (address target, uint256 value, bytes memory data) = abi.decode(
            callData[4:],
            (address, uint256, bytes)
        );

        uint256 keyVersion = registry.getKeyVersion(address(this));

        bytes memory encoded = abi.encode(
            "HYQUB_TX_V1",
            block.chainid,
            address(this),
            target,
            value,
            data,
            keyVersion
        );

        return sha256(encoded);
    }

    // ------------------------------------------------------------------
    // View Functions
    // ------------------------------------------------------------------

    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }
}
