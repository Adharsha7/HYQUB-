// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/HYQUBWallet.sol";
import "../src/HYQUBRegistry.sol";
import {EntryPoint} from "account-abstraction/core/EntryPoint.sol";
import {PackedUserOperation} from "account-abstraction/interfaces/PackedUserOperation.sol";

contract EntryPointIntegrationTest is Test {
    EntryPoint entryPoint;
    HYQUBWallet wallet;
    HYQUBRegistry registry;

    uint256 signerPrivateKey = 0xA11CE;
    address approvalSigner;

    address target = address(0x4444444444444444444444444444444444444444);
    address beneficiary = address(0xB0B);
    address bundler = address(0xBEEF00000000000000000000000000000000EE);

    function setUp() public {
        approvalSigner = vm.addr(signerPrivateKey);

        entryPoint = new EntryPoint();
        registry = new HYQUBRegistry();
        wallet = new HYQUBWallet(
            address(registry),
            approvalSigner,
            address(entryPoint)
        );

        registry.registerWallet(address(wallet), bytes32(uint256(1)));
        // keyVersion is 1 immediately after registration (no rotation needed
        // here — keeping this test independent from the rotation tests).

        // Fund the wallet's own ETH balance (used by execute() to send value).
        vm.deal(address(wallet), 1 ether);

        // Fund this test contract, then deposit into the wallet's EntryPoint
        // balance (used to cover validation/execution gas prefund).
        vm.deal(address(this), 5 ether);
        wallet.addDeposit{value: 1 ether}();

        // Give the EntryPoint's gas-cost math a stable, low gas price.
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

    function _buildValidUserOp(
        uint256 value,
        uint256 approvalNonce
    ) internal view returns (PackedUserOperation memory) {
        bytes memory data = "";

        bytes memory callData = abi.encodeWithSelector(
            HYQUBWallet.execute.selector,
            target,
            value,
            data
        );

        uint256 keyVersion = registry.getKeyVersion(address(wallet));

        bytes memory transactionIntent = abi.encode(
            "HYQUB_TX_V1",
            block.chainid,
            address(wallet),
            target,
            value,
            data,
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

        return PackedUserOperation({
            sender: address(wallet),
            nonce: 0,
            initCode: "",
            callData: callData,
            accountGasLimits: _packGasLimits(300_000, 150_000), // verification, call
            preVerificationGas: 50_000,
            gasFees: _packGasLimits(1 gwei, 10 gwei), // priority, max
            paymasterAndData: "",
            signature: signature
        });
    }

    function test_HandleOpsExecutesApprovedTransfer() public {
        uint256 value = 0.01 ether;
        PackedUserOperation memory userOp = _buildValidUserOp(value, 1);

        uint256 targetBalanceBefore = target.balance;

        PackedUserOperation[] memory ops = new PackedUserOperation[](1);
        ops[0] = userOp;

        // handleOps requires tx.origin == msg.sender and msg.sender to be
        // an EOA (code.length == 0) — this models a real bundler calling
        // in directly, not via another contract. vm.prank(a, b) sets both
        // msg.sender and tx.origin for the next external call.
        vm.prank(bundler, bundler);
        entryPoint.handleOps(ops, payable(beneficiary));

        assertEq(target.balance, targetBalanceBefore + value);
        assertTrue(wallet.usedApprovalNonces(1));
        assertEq(wallet.nonce(), 1); // incremented inside execute()
    }
}
