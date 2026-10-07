// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/HYQUBWallet.sol";
import "../src/HYQUBRegistry.sol";
import "../src/TestTarget.sol";
import {EntryPoint} from "account-abstraction/core/EntryPoint.sol";
import {PackedUserOperation} from "account-abstraction/interfaces/PackedUserOperation.sol";

contract EntryPointCalldataIntegrationTest is Test {
    EntryPoint entryPoint;
    HYQUBWallet wallet;
    HYQUBRegistry registry;
    TestTarget testTarget;

    uint256 signerPrivateKey = 0xA11CE;
    address approvalSigner;

    address beneficiary = address(0xB0B);
    address bundler = address(0xBEEF00000000000000000000000000000000EE);

    function setUp() public {
        approvalSigner = vm.addr(signerPrivateKey);

        entryPoint = new EntryPoint();
        registry = new HYQUBRegistry();
        testTarget = new TestTarget();
        wallet = new HYQUBWallet(
            address(registry),
            approvalSigner,
            address(entryPoint)
        );

        registry.registerWallet(address(wallet), bytes32(uint256(1)));

        vm.deal(address(wallet), 1 ether);
        vm.deal(address(this), 5 ether);
        wallet.addDeposit{value: 1 ether}();

        vm.txGasPrice(1 gwei);
    }

    function _sign(bytes32 payloadHash) internal view returns (bytes memory) {
        bytes32 ethSignedMessageHash = keccak256(
            abi.encodePacked("\x19Ethereum Signed Message:\n32", payloadHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, ethSignedMessageHash);
        return abi.encodePacked(r, s, v);
    }

    function _packGasLimits(uint128 hi, uint128 lo) internal pure returns (bytes32) {
        return bytes32((uint256(hi) << 128) | uint256(lo));
    }

    /// @dev Builds a UserOp whose approval is signed for `approvedValueArg`,
    ///      but whose actual callData encodes `submittedValueArg`. Passing
    ///      the same value for both produces a normal, honestly-approved op.
    function _buildUserOp(
        uint256 approvedValueArg,
        uint256 submittedValueArg,
        uint256 approvalNonce
    ) internal view returns (PackedUserOperation memory) {
        // What the backend actually approved:
        bytes memory approvedData = abi.encodeCall(TestTarget.setValue, (approvedValueArg));

        uint256 keyVersion = registry.getKeyVersion(address(wallet));

        bytes memory transactionIntent = abi.encode(
            "HYQUB_TX_V1",
            block.chainid,
            address(wallet),
            address(testTarget),
            uint256(0),
            approvedData,
            keyVersion
        );
        bytes32 messageHash = sha256(transactionIntent);

        bytes memory approvalPayload = abi.encode(
            "HYQUB_APPROVAL_V1",
            address(wallet),
            messageHash,
            keyVersion,
            approvalNonce,
            block.timestamp,
            new string[](0)
        );

        bytes32 approvalHash = sha256(approvalPayload);
        bytes memory approvalSignature = _sign(approvalHash);
        bytes memory signature = abi.encode(approvalPayload, approvalSignature);

        // What is actually submitted on-chain — may differ from what was approved:
        bytes memory submittedData = abi.encodeCall(TestTarget.setValue, (submittedValueArg));
        bytes memory callData = abi.encodeWithSelector(
            HYQUBWallet.execute.selector,
            address(testTarget),
            uint256(0),
            submittedData
        );

        return PackedUserOperation({
            sender: address(wallet),
            nonce: 0,
            initCode: "",
            callData: callData,
            accountGasLimits: _packGasLimits(300_000, 150_000),
            preVerificationGas: 50_000,
            gasFees: _packGasLimits(1 gwei, 10 gwei),
            paymasterAndData: "",
            signature: signature
        });
    }

    function test_ApprovedContractCallSucceeds() public {
        PackedUserOperation memory userOp = _buildUserOp(123, 123, 1);

        PackedUserOperation[] memory ops = new PackedUserOperation[](1);
        ops[0] = userOp;

        vm.prank(bundler, bundler);
        entryPoint.handleOps(ops, payable(beneficiary));

        assertEq(testTarget.value(), 123);
    }

    function test_TamperedCalldataAfterApprovalIsRejected() public {
        // Approval was signed for setValue(123), but the submitted
        // UserOp's callData actually calls setValue(999).
        PackedUserOperation memory userOp = _buildUserOp(123, 999, 2);

        PackedUserOperation[] memory ops = new PackedUserOperation[](1);
        ops[0] = userOp;

        // validateUserOp correctly returns SIG_VALIDATION_FAILED for this
        // tampered op. For a real (non-simulation) handleOps call, the
        // EntryPoint itself reverts the whole batch with FailedOp rather
        // than silently skipping the op — this is the actual, stronger
        // on-chain behavior, and confirms the tamper was caught.
        vm.expectRevert(
            abi.encodeWithSelector(
                bytes4(keccak256("FailedOp(uint256,string)")),
                uint256(0),
                "AA24 signature error"
            )
        );

        vm.prank(bundler, bundler);
        entryPoint.handleOps(ops, payable(beneficiary));

        // Since the whole transaction reverted, setValue was never called.
        assertEq(testTarget.value(), 0);
    }
}
